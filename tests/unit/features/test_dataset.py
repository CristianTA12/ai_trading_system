import numpy as np
import pandas as pd
import pytest

from src.features.dataset import (
    STEP,
    aggregate_minutes,
    build_features,
    build_labels,
    temporal_splits,
)


def bars_frame(count=240, start="2023-12-30"):
    index = pd.date_range(start, periods=count, freq="15min", tz="UTC")
    close = 100 + np.arange(count) * 0.2 + np.sin(np.arange(count) / 3)
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 10 + np.arange(count) % 7,
            "trades": 20 + np.arange(count) % 5,
        },
        index=index,
    )


def test_complete_minute_aggregation_and_missing_minute():
    frame = bars_frame(45)
    frame.index = pd.date_range("2024-01-01", periods=45, freq="min", tz="UTC")
    result = aggregate_minutes(frame)
    assert len(result) == 3
    assert result.iloc[0]["open"] == frame.iloc[0]["open"]
    assert result.iloc[0]["close"] == frame.iloc[14]["close"]
    assert result.iloc[0]["high"] == frame.iloc[:15]["high"].max()
    assert result.iloc[0]["volume"] == frame.iloc[:15]["volume"].sum()
    result = aggregate_minutes(frame.drop(frame.index[20]))
    assert len(result) == 2
    assert pd.Timestamp("2024-01-01 00:15", tz="UTC") not in result.index


def test_availability_warmup_and_known_returns():
    bars = bars_frame()
    features = build_features(bars)
    assert features.index[0] == bars.index[49] + STEP
    assert features.index[-1] == bars.index[-1] + STEP
    expected = bars["close"].iloc[49] / bars["close"].iloc[45] - 1
    assert features.iloc[0]["return_4"] == pytest.approx(expected)
    assert np.isfinite(features.to_numpy()).all()
    assert not any("target" in c for c in features.columns)


def test_future_changes_do_not_change_past_features():
    bars = bars_frame()
    reference = build_features(bars)
    changed = bars.copy()
    changed.loc[changed.index[150] :, ["open", "high", "low", "close", "volume"]] *= 7
    after = build_features(changed)
    cutoff = bars.index[150]
    pd.testing.assert_frame_equal(reference.loc[:cutoff], after.loc[:cutoff])
    pd.testing.assert_frame_equal(build_features(bars.iloc[:150]), reference.loc[:cutoff])


def test_gap_restarts_all_rolling_and_ewm_state():
    bars = bars_frame().drop(bars_frame().index[100])
    features = build_features(bars)
    post_gap = bars.loc[bars.index[100] :]
    fresh = build_features(post_gap)
    pd.testing.assert_frame_equal(features.loc[fresh.index], fresh)
    assert not features.index.isin(post_gap.index[:49] + STEP).any()


def test_constant_market_is_finite_and_neutral():
    bars = bars_frame()
    bars.loc[:, ["open", "high", "low", "close"]] = 100
    bars.loc[:, ["volume", "trades"]] = 0
    features = build_features(bars)
    assert (features["rsi_14_cutler"] == 50).all()
    assert (features["return_1"] == 0).all()
    assert (features["volume_zscore_20"] == 0).all()
    assert np.isfinite(features.to_numpy()).all()


def test_labels_use_next_bar_and_do_not_bridge_gaps():
    bars = bars_frame().drop(bars_frame().index[150])
    features = build_features(bars)
    labels = build_labels(bars, features.index)
    moment = features.index[0]
    assert labels.loc[moment, "entry_open"] == bars.loc[moment, "open"]
    assert labels.loc[moment, "label_end"] == moment + STEP
    assert labels.loc[moment, "target_return_next_15m"] == pytest.approx(
        bars.loc[moment, "close"] / bars.loc[moment, "open"] - 1
    )
    assert bars_frame().index[150] not in labels.index
    assert features.index[-1] not in labels.index


def test_split_purges_outcomes_at_boundaries():
    index = pd.DatetimeIndex(
        ["2023-12-31 23:45", "2024-01-01 00:00", "2024-12-31 23:45", "2025-01-01 00:00"], tz="UTC"
    )
    labels = pd.DataFrame({"label_end": index + STEP}, index=index)
    result = temporal_splits(labels, "2024-01-01", "2025-01-01")
    assert result["split"].tolist() == ["purged", "validation", "purged", "test"]


def test_bad_index_rejected():
    bars = bars_frame()
    with pytest.raises(ValueError, match="ordenadas"):
        build_features(bars.iloc[::-1])
    bars.index = bars.index + pd.Timedelta(minutes=1)
    with pytest.raises(ValueError, match="alineadas"):
        build_features(bars)
