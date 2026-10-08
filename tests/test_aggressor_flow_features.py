import numpy as np
import pandas as pd
import pytest

from src.features.aggressor_flow import FLOW_COLUMNS, aggregate_flow, align_flow


def minutes():
    index = pd.date_range("2020-01-01", periods=120, freq="min", tz="UTC")
    return pd.DataFrame({"volume": 10.0, "taker_base": 7.0}, index=index)


def test_missing_minute_invalidates_whole_bar():
    source = minutes()
    bars = aggregate_flow(source.drop(source.index[10]))
    assert source.index[0] not in bars.index
    assert len(bars) == 7


def test_latest_bar_is_excluded_and_future_cannot_change_features():
    source = minutes()
    decisions = pd.DatetimeIndex(["2020-01-01 01:15Z"])
    expected = align_flow(decisions, aggregate_flow(source))
    source.loc[source.index >= "2020-01-01 01:00Z", "taker_base"] = 0
    pd.testing.assert_frame_equal(expected, align_flow(decisions, aggregate_flow(source)))
    assert np.allclose(expected[FLOW_COLUMNS], 0.4)
    assert expected.latest_source_close.iloc[0] < decisions[0]


def test_hour_is_ratio_of_sums_not_mean_of_ratios():
    source = minutes()
    source.loc[source.index < "2020-01-01 00:15Z", ["volume", "taker_base"]] = [100, 0]
    decisions = pd.DatetimeIndex(["2020-01-01 01:15Z"])
    result = align_flow(decisions, aggregate_flow(source))
    assert np.isclose(result.flow_imbalance_1h.iloc[0], (2 * 315 - 1950) / 1950)


def test_gap_is_not_forward_filled_and_zero_is_missing():
    source = minutes()
    decisions = pd.DatetimeIndex(["2020-01-01 01:15Z"])
    bars = aggregate_flow(source)
    result = align_flow(decisions, bars.drop(bars.index[1]))
    assert not result.eligible_under_assumption.iloc[0]
    source[["volume", "taker_base"]] = 0
    assert align_flow(decisions, aggregate_flow(source))[FLOW_COLUMNS].isna().all().all()


def test_invalid_volume_rejected():
    source = minutes()
    source.iloc[0, 1] = 11
    with pytest.raises(ValueError):
        aggregate_flow(source)
