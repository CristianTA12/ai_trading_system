import numpy as np
import pandas as pd

from src.features.dataset import STEP, build_features
from src.features.lags import LAG_COLUMNS, build_lag_features
from src.features.regime import build_regime_features
from src.training.regime_experiment import acceptance


def bars(count=240):
    index = pd.date_range("2020-01-01", periods=count, freq="15min", tz="UTC")
    close = 100 + np.arange(count) * 0.01 + np.sin(np.arange(count) / 5)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 10,
            "trades": 5,
        },
        index=index,
    )


def test_exactly_three_lags_preserve_v1_and_cost_four_rows():
    data = bars()
    base = build_features(data)
    result = build_lag_features(data, base)
    assert len(result.columns) == 23
    assert list(result.columns[-3:]) == LAG_COLUMNS
    assert len(base) - len(result) == 4
    assert result.index[0] == base.index[0] + 4 * STEP
    pd.testing.assert_frame_equal(result[base.columns], base.loc[result.index])
    for column, source, shift in (
        (LAG_COLUMNS[0], "return_1", 1),
        (LAG_COLUMNS[1], "return_1", 4),
        (LAG_COLUMNS[2], "rsi_14_cutler", 1),
    ):
        np.testing.assert_allclose(result[column], base[source].shift(shift).loc[result.index])


def test_lags_reset_after_gap_without_extra_long_warmup():
    data = bars()
    restart = data.index[121]
    data = data.drop(data.index[120])
    base = build_features(data)
    result = build_lag_features(data, base)
    assert len(base) - len(result) == 8
    first_base_after = base.index[base.index >= restart][0]
    first_lag_after = result.index[result.index >= restart][0]
    assert first_lag_after == first_base_after + 4 * STEP


def test_missing_feature_row_does_not_compress_lag_clock():
    data = bars()
    base = build_features(data)
    missing = base.index[-10]
    result = build_lag_features(data, base.drop(missing))
    assert missing + STEP not in result.index
    assert missing + 4 * STEP not in result.index
    assert missing + 5 * STEP in result.index
    assert result.loc[missing + 5 * STEP, "return_1_lag_4"] == base.loc[missing + STEP, "return_1"]


def test_future_mutation_and_truncation_leave_past_lags_unchanged():
    data = bars()
    original = build_lag_features(data, build_features(data))
    cutoff = data.index[180]
    changed = data.copy()
    changed.loc[cutoff:, ["open", "high", "low", "close"]] *= 2
    modified = build_lag_features(changed, build_features(changed))
    pd.testing.assert_frame_equal(original.loc[:cutoff], modified.loc[:cutoff])
    truncated = data.loc[data.index < cutoff]
    prefix = build_lag_features(truncated, build_features(truncated))
    pd.testing.assert_frame_equal(original.loc[prefix.index], prefix)


def test_ablation_uses_identical_lag_values_to_v2():
    data = bars(3000)
    base = build_features(data)
    lags = build_lag_features(data, base)
    v2 = build_regime_features(data, base)
    pd.testing.assert_frame_equal(lags.loc[v2.index, LAG_COLUMNS], v2[LAG_COLUMNS])


def test_lags_keep_the_historical_gate_and_separate_decision_name():
    rows = [
        {"arm": arm, "fold": str(i), "scenario": "net", "total_return": value}
        for arm in ("v1_matched", "lags")
        for i, value in enumerate([0.1, 0.2, 0, -0.1])
    ]
    report = acceptance(rows, "lags")
    assert report["positive_folds"] == {"v1_matched": 2, "lags": 2}
    assert not report["lags_passes_preregistered_gate"]
    assert "v2_passes_preregistered_gate" not in report
    rows[-2]["total_return"] = 0.00001
    assert acceptance(rows, "lags")["lags_passes_preregistered_gate"]
