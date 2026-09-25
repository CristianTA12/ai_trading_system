import numpy as np
import pandas as pd
import pytest

from src.backtesting.dataset import ExperimentData
from src.features.dataset import STEP, build_features
from src.features.regime import NEW_COLUMNS, PEAK_WINDOW, build_regime_features
from src.training.regime_experiment import acceptance, paired_folds


def bars(count=3000, constant=False):
    index = pd.date_range("2020-01-01", periods=count, freq="15min", tz="UTC")
    close = np.full(count, 100.0) if constant else 100 + np.arange(count) * 0.1
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": 10.0, "trades": 5},
        index=index,
    )


def test_v2_formulas_lags_and_preserved_v1():
    data = bars()
    base = build_features(data)
    result = build_regime_features(data, base)
    assert len(result.columns) == 25
    assert list(result.columns[-5:]) == NEW_COLUMNS
    assert result.index[0] == data.index[0] + PEAK_WINDOW * STEP
    pd.testing.assert_frame_equal(result[base.columns], base.loc[result.index])
    np.testing.assert_allclose(result.trend_strength_96, 1)
    np.testing.assert_allclose(result.drawdown_from_peak_2880, 0)
    for column, source, lag in (
        ("return_1_lag_1", "return_1", 1),
        ("return_1_lag_4", "return_1", 4),
        ("rsi_14_cutler_lag_1", "rsi_14_cutler", 1),
    ):
        np.testing.assert_allclose(result[column], base[source].shift(lag).loc[result.index])


def test_peak_is_trailing_not_global_and_flat_trend_is_zero():
    data = bars(PEAK_WINDOW + 2, constant=True)
    data.iloc[0, data.columns.get_loc("high")] = 200
    result = build_regime_features(data, build_features(data))
    assert result.drawdown_from_peak_2880.iloc[0] == -0.5
    assert result.drawdown_from_peak_2880.iloc[1] == 0
    assert (result.trend_strength_96 == 0).all()
    assert np.isfinite(result.to_numpy()).all()


def test_future_changes_and_truncation_do_not_change_past():
    data = bars(3400)
    result = build_regime_features(data, build_features(data))
    cutoff = data.index[3200]
    changed = data.copy()
    changed.loc[cutoff:, ["open", "high", "low", "close"]] *= 0.5
    modified = build_regime_features(changed, build_features(changed))
    pd.testing.assert_frame_equal(result.loc[:cutoff], modified.loc[:cutoff])
    truncated = data.loc[data.index < cutoff]
    prefix = build_regime_features(truncated, build_features(truncated))
    pd.testing.assert_frame_equal(result.loc[prefix.index], prefix)


def test_windows_and_lags_restart_after_gap():
    data = bars(5900)
    restart = data.index[2901]
    data = data.drop(data.index[2900])
    result = build_regime_features(data, build_features(data))
    after = result.loc[result.index >= restart]
    assert after.index[0] == restart + PEAK_WINDOW * STEP
    assert result.loc[(result.index >= restart) & (result.index < after.index[0])].empty


def test_paired_folds_have_identical_train_labels_and_prediction_coverage():
    index = pd.date_range("2020-01-01", "2023-12-31", freq="1D", tz="UTC")
    base = pd.DataFrame({"a": np.arange(len(index))}, index=index)
    returns = pd.Series(np.resize([0.01, 0, -0.01], len(index)), index=index)
    empty = base.iloc[:0]
    data = ExperimentData(
        {"train_end": "2024-01-01"}, base, returns, empty, returns.iloc[:0], empty, empty, base
    )
    features = base.iloc[30:].drop(base.index[::7], errors="ignore").assign(regime=1)
    folds = list(paired_folds(data, features))
    assert len(folds) == 4
    for _, control, candidate in folds:
        assert control.train_features.index.equals(candidate.train_features.index)
        assert control.validation_features.index.equals(candidate.validation_features.index)
        pd.testing.assert_series_equal(control.train_returns, candidate.train_returns)
        pd.testing.assert_frame_equal(control.train_features, candidate.train_features[["a"]])
        assert (
            candidate.train_features.index.max() + STEP < candidate.validation_features.index.min()
        )
        assert candidate.validation_features.index.max() < pd.Timestamp("2024-01-01", tz="UTC")


def test_acceptance_is_three_of_four_strictly_positive_not_zero():
    rows = [
        {"arm": arm, "fold": str(i), "scenario": "net", "total_return": value}
        for arm in ("v1_matched", "v2")
        for i, value in enumerate([0.1, 0.2, 0, -0.1])
    ]
    assert not acceptance(rows)["v2_passes_preregistered_gate"]
    rows[6]["total_return"] = 0.00001
    decision = acceptance(rows)
    assert decision["v2_passes_preregistered_gate"]
    assert decision["positive_folds"] == {"v1_matched": 2, "v2": 3}
    assert not decision["promoted"]
    with pytest.raises(ValueError):
        acceptance(rows[:-1])
