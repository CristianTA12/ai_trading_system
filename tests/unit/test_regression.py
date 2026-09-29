import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBRegressor

from src.backtesting.dataset import ExperimentData
from src.backtesting.engine import run_backtest
from src.backtesting.policies import policy_metrics
from src.models.xgboost.classifier import ModelConfig
from src.models.xgboost.regressor import (
    fit_predict_regression,
    regression_diagnostics,
    regression_targets,
)
from src.training.regression_experiment import fold_result


def test_regression_hysteresis_and_exact_boundaries():
    index = pd.date_range("2022-01-01", periods=9, freq="15min", tz="UTC")
    prediction = pd.Series(
        [0.00149, 0.0015, -0.01, -0.01, -0.01, 0, 0.0001, -0.001, 0.0015], index=index
    )
    assert regression_targets(index, prediction).tolist() == [0, 1, 1, 1, 1, 1, 1, 0, 1]


def test_missing_prediction_forces_flat_inside_hold():
    index = pd.date_range("2022-01-01", periods=3, freq="15min", tz="UTC")
    prediction = pd.Series([0.0015, np.nan, 0.001], index=index)
    assert regression_targets(index, prediction).tolist() == [1, 0, 0]
    assert regression_targets(index, prediction.dropna()).tolist() == [1, 0, 0]


def test_regression_policy_causal_and_elapsed_time():
    index = pd.to_datetime(["2022-01-01 00:00Z", "2022-01-01 01:00Z", "2022-01-01 01:15Z"])
    prediction = pd.Series([0.002, -0.001, 0.002], index=index)
    assert regression_targets(index, prediction).tolist() == [1, 0, 1]
    altered = prediction.copy()
    altered.iloc[-1] = -0.01
    pd.testing.assert_series_equal(
        regression_targets(index, prediction).iloc[:2], regression_targets(index, altered).iloc[:2]
    )


def test_regression_diagnostics_baselines_and_empty_selection():
    report = regression_diagnostics([0.01, -0.01], [0.0, 0.0], 0.005)
    assert report["zero_mae"] == pytest.approx(0.01)
    assert report["train_mean_rmse"] == pytest.approx(np.sqrt((0.005**2 + 0.015**2) / 2))
    assert report["correlation"] is None
    assert report["signal_count"] == 0
    assert report["selected_realized_mean"] is None


def synthetic_data():
    rng = np.random.default_rng(42)
    train_index = pd.date_range("2020-01-01", periods=90, freq="15min", tz="UTC")
    eval_index = pd.date_range("2022-01-01", periods=12, freq="15min", tz="UTC")
    columns = [f"feature_{i}" for i in range(20)]
    train = pd.DataFrame(rng.normal(size=(90, 20)), index=train_index, columns=columns)
    evaluation = pd.DataFrame(rng.normal(size=(12, 20)), index=eval_index, columns=columns)
    returns = pd.Series(np.resize([-0.004, 0.0, 0.004], 90), index=train_index)
    outcomes = pd.Series(np.resize([-0.004, 0.0, 0.004], 12), index=eval_index)
    bars = pd.DataFrame(
        {"open": 100.0, "close": 100 * (1 + outcomes), "high": 101.0, "low": 99.0}, index=eval_index
    )
    return ExperimentData(
        {"sha256": {}, "train_end": "2024-01-01"},
        train,
        returns,
        evaluation,
        outcomes,
        bars,
        evaluation,
    )


def test_regression_fit_only_train_and_reload(tmp_path, monkeypatch):
    data = synthetic_data()
    original = XGBRegressor.fit

    def spy(self, x, y, **kwargs):
        pd.testing.assert_frame_equal(x, data.train_features)
        pd.testing.assert_series_equal(y, data.train_returns)
        assert not kwargs  # Neither class weights nor validation/early stopping.
        return original(self, x, y, **kwargs)

    monkeypatch.setattr(XGBRegressor, "fit", spy)
    model, predictions, diagnostics = fit_predict_regression(
        data, ModelConfig(n_estimators=2, n_jobs=1)
    )
    assert predictions.index.equals(data.validation_features.index)
    assert diagnostics["train_mean"] == pytest.approx(data.train_returns.mean())
    model.save_model(tmp_path / "model.ubj")
    restored = XGBRegressor()
    restored.load_model(tmp_path / "model.ubj")
    np.testing.assert_array_equal(
        restored.predict(data.validation_features), predictions.predicted_return
    )


def test_cash_adapter_requires_no_positions_or_fills():
    data = synthetic_data()
    result = run_backtest(data.validation_bars, pd.Series(0, index=data.validation_bars.index))
    assert fold_result("2022 H1", result, policy_metrics(result)).is_cash
    altered = replace(result, equity=result.equity.copy())
    altered.equity.iloc[1, altered.equity.columns.get_loc("quantity")] = 1
    assert not fold_result("2022 H1", altered, policy_metrics(altered)).is_cash


def test_complete_paired_runner_artifacts(tmp_path, monkeypatch):
    from src.training import regression_experiment as runner

    data = synthetic_data()
    monkeypatch.setattr(
        runner, "load_dataset", lambda path, *, train_only: data if train_only else None
    )

    def windows(_data):
        for start in ("2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01"):
            index = pd.date_range(start, periods=12, freq="15min", tz="UTC")
            yield (
                start,
                replace(
                    data,
                    validation_features=data.validation_features.set_axis(index),
                    validation_returns=data.validation_returns.set_axis(index),
                    validation_bars=data.validation_bars.set_axis(index),
                ),
            )

    monkeypatch.setattr(runner, "training_folds", windows)
    monkeypatch.setattr(
        runner, "ModelConfig", lambda **kw: ModelConfig(n_estimators=2, n_jobs=1, **kw)
    )
    monkeypatch.setattr(runner, "plot_curves", lambda *args: None)
    output = tmp_path / "run"
    report = runner.run_iteration(tmp_path, output, tracking_uri=None)
    assert report["test_evaluated"] is False
    assert set(report["decision"]) == {"regression", "classifier"}
    assert len(list(output.rglob("model.ubj"))) == 40
    comparison = pd.read_csv(output / "comparison.csv")
    assert len(comparison) == 128  # 40 models * 3 scenarios + 8 benchmark rows.
    verdict = json.loads((output / "regression_verdict.json").read_text())
    assert verdict["seeds_total"] == 5
    assert all(len(seed["folds"]) == 4 for seed in verdict["seeds"])
    for arm in runner.ARMS:
        predictions = pd.read_parquet(output / "seed_42" / "2022 H1" / arm / "predictions.parquet")
        pd.testing.assert_series_equal(
            predictions.actual_return, data.validation_returns, check_names=False, check_freq=False
        )
