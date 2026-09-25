from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBClassifier

from src.backtesting.dataset import ExperimentData
from src.backtesting.engine import ExecutionConfig, run_backtest
from src.backtesting.policies import multiclass_policies, stateful_targets
from src.models.xgboost.classifier import ModelConfig, position_targets
from src.models.xgboost.hourly import HORIZON, binary_labels, fit_hourly, hourly_labels
from src.training.exit_horizon import hourly_folds


def predictions(classes):
    index = pd.date_range("2023-01-01", periods=len(classes), freq="15min", tz="UTC")
    probability = np.full((len(classes), 3), 0.1)
    for i, label in enumerate(classes):
        probability[i, label] = 0.8
    return pd.DataFrame(probability, index=index, columns=["p_down", "p_neutral", "p_up"])


def test_minimum_hold_down_only_and_combination():
    data = predictions([2, 1, 0, 1, 1, 0, 2, 1])
    targets = multiclass_policies(data.index, data)
    assert targets["baseline"].tolist() == [1, 0, 0, 0, 0, 0, 1, 0]
    assert targets["hold_60m"].tolist() == [1, 1, 1, 1, 0, 0, 1, 1]
    assert targets["exit_down"].tolist() == [1, 1, 0, 0, 0, 0, 1, 1]
    assert targets["hold_60m_exit_down"].tolist() == [1, 1, 1, 1, 1, 0, 1, 1]
    pd.testing.assert_series_equal(targets["baseline"], position_targets(data, 0.5))


def test_minimum_hold_missing_signal_and_period_end_exceptions():
    data = predictions([2, 1, 1])
    targets = multiclass_policies(data.index, data.drop(data.index[1]))
    assert targets["hold_60m"].tolist() == [1, 0, 0]
    prices = pd.DataFrame(
        {name: 100 for name in ("open", "high", "low", "close")}, index=data.index
    )
    result = run_backtest(
        prices, multiclass_policies(data.index, data)["hold_60m"], ExecutionConfig()
    )
    assert result.trades.reason.iloc[0] == "end_of_period"
    assert (
        result.trades.exit_time.iloc[0] - result.trades.entry_time.iloc[0]
    ).total_seconds() == 45 * 60


def test_holding_uses_elapsed_time_and_is_causal():
    data = predictions([2, 0, 0, 0, 0, 0])
    original = multiclass_policies(data.index, data)
    changed = data.copy()
    changed.iloc[4:] = [0.1, 0.1, 0.8]
    modified = multiclass_policies(data.index, changed)
    for name in original:
        pd.testing.assert_series_equal(original[name].iloc[:4], modified[name].iloc[:4])
    sparse = data.iloc[[0, 4, 5]]
    assert multiclass_policies(sparse.index, sparse)["hold_60m"].tolist() == [1, 0, 0]


def test_hourly_target_prices_gaps_and_boundary():
    index = pd.date_range("2023-01-01", periods=8, freq="15min", tz="UTC")
    bars = pd.DataFrame(
        {"open": 100, "close": [100, 101, 102, 104, 105, 106, 107, 108]}, index=index
    )
    labels = hourly_labels(bars, index)
    assert labels.target_return.iloc[0] == pytest.approx(0.04)
    assert labels.label_end.iloc[0] == index[0] + HORIZON
    assert len(labels) == 5
    gapped = hourly_labels(bars.drop(index[2]), index)
    assert index[0] not in gapped.index and index[1] not in gapped.index
    assert index[3] in gapped.index
    np.testing.assert_array_equal(binary_labels(pd.Series([-0.01, 0, 0.005, 0.0051])), [0, 0, 0, 1])


def hourly_test_data():
    index = pd.date_range("2020-01-01", "2024-01-01", freq="15min", inclusive="left", tz="UTC")
    features = pd.DataFrame({"x": np.arange(len(index), dtype=float)}, index=index)
    bars = pd.DataFrame({"open": 100, "close": 101}, index=index)
    empty = features.iloc[:0]
    data = ExperimentData(
        {"train_end": "2024-01-01"},
        features,
        pd.Series(0, index=index),
        empty,
        pd.Series(dtype=float, index=empty.index),
        empty,
        empty,
        bars,
    )
    return data


def test_hourly_folds_purge_full_horizon_without_predicting_future_gaps():
    data = hourly_test_data()
    missing = pd.Timestamp("2022-02-01 00:45", tz="UTC")
    data = replace(data, train_bars=data.train_bars.drop(missing))
    labels = hourly_labels(data.train_bars, data.train_features.index)
    folds = list(hourly_folds(data, labels))
    assert len(folds) == 4
    for _, fold in folds:
        assert fold.train_features.index.max() + HORIZON < fold.validation_features.index.min()
        assert fold.validation_features.index.max() + HORIZON < pd.Timestamp("2024-01-01", tz="UTC")
        assert not fold.train_returns.isna().any()
    first = folds[0][1]
    assert missing - pd.Timedelta(minutes=45) in first.validation_features.index
    assert pd.isna(first.validation_returns.loc[missing - pd.Timedelta(minutes=45)])


def test_binary_fit_train_only_and_predictions_survive_unscorable_outcome(monkeypatch):
    index = pd.date_range("2021-01-01", periods=30, freq="15min", tz="UTC")
    train = pd.DataFrame({"x": np.arange(30, dtype=float)}, index=index)
    evaluation = train.iloc[:3].copy()
    evaluation.index += pd.Timedelta(days=365)
    data = ExperimentData(
        {},
        train,
        pd.Series(np.resize([0, 0.01], 30), index=index),
        evaluation,
        pd.Series([np.nan, 0, 0.01], index=evaluation.index),
        evaluation,
        evaluation,
    )
    fit = XGBClassifier.fit

    def spy(self, x, y, **kwargs):
        assert x.index.equals(train.index)
        assert "eval_set" not in kwargs
        return fit(self, x, y, **kwargs)

    monkeypatch.setattr(XGBClassifier, "fit", spy)
    _, predicted, report = fit_hourly(data, ModelConfig(threshold=0.005, n_estimators=3))
    assert predicted.index.equals(evaluation.index)
    assert report["scored_rows"] == 2
    assert report["predictions_without_complete_outcome"] == 1


def test_bad_exit_signals_rejected():
    data = predictions([2, 1])
    with pytest.raises(ValueError):
        stateful_targets(
            data.index, pd.Series([1, np.nan], index=data.index), pd.Series(False, index=data.index)
        )
