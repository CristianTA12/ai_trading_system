from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBClassifier

from src.backtesting.dataset import ExperimentData
from src.backtesting.regime_gate import gated_targets
from src.models.xgboost.classifier import ModelConfig, encode_classes, fit_predict
from src.models.xgboost.four_hour import HORIZON, four_hour_labels, paired_horizon_folds


def test_target_prices_sixteen_bars_and_end():
    index = pd.date_range("2022-01-01", periods=20, freq="15min", tz="UTC")
    bars = pd.DataFrame(
        {"open": np.arange(100.0, 120.0), "close": np.arange(101.0, 121.0)}, index=index
    )
    labels = four_hour_labels(bars, index)
    assert len(labels) == 5
    assert labels.iloc[0].target_return == pytest.approx(116 / 100 - 1)
    assert labels.iloc[0].label_end == index[0] + HORIZON
    changed = bars.copy()
    changed.loc[index[16] :, "close"] = 999
    assert four_hour_labels(changed, index).iloc[0].target_return == labels.iloc[0].target_return
    assert (
        four_hour_labels(bars.iloc[:16], index).iloc[0].target_return
        == labels.iloc[0].target_return
    )


def test_future_gap_invalidates_labels_not_bridges():
    index = pd.date_range("2022-01-01", periods=35, freq="15min", tz="UTC")
    bars = pd.DataFrame({"open": 100.0, "close": 101.0}, index=index).drop(index[10])
    labels = four_hour_labels(bars, index)
    assert not index[:11].isin(labels.index).any()
    assert index[11] in labels.index
    np.testing.assert_array_equal(
        encode_classes(pd.Series([-0.0101, -0.01, 0, 0.01, 0.0101]), 0.01), [0, 1, 1, 1, 2]
    )


def test_paired_train_purge_and_predictions_without_future_outcome():
    index = pd.date_range("2020-01-01", "2024-01-01", freq="15min", inclusive="left", tz="UTC")
    features = pd.DataFrame({"x": np.arange(len(index))}, index=index)
    bars = pd.DataFrame({"open": 100.0, "close": 101.0}, index=index)
    missing = pd.Timestamp("2022-02-01 02:00", tz="UTC")
    bars = bars.drop(missing)
    features = features.drop(missing)
    data = ExperimentData(
        {"train_end": "2024-01-01"},
        features,
        pd.Series(0.01, index=features.index),
        features.iloc[:0],
        pd.Series(dtype=float),
        bars.iloc[:0],
        features.iloc[:0],
        bars,
    )
    labels = four_hour_labels(bars, features.index)
    windows = list(paired_horizon_folds(data, labels))
    for start, short, long in windows:
        assert short.train_features.equals(long.train_features)
        assert short.validation_features.equals(long.validation_features)
        assert not long.train_returns.isna().any()
        assert (long.train_features.index + HORIZON < pd.Timestamp(start, tz="UTC")).all()
        assert long.validation_features.index.max() + HORIZON <= long.validation_bars.index.max()
    t = missing - pd.Timedelta(hours=1)
    assert t in windows[0][2].validation_features.index
    assert pd.isna(windows[0][2].validation_returns.loc[t])
    assert t not in windows[1][2].train_features.index


def test_multiclass_predicts_unscorable_rows_without_using_eval_for_fit(monkeypatch):
    index = pd.date_range("2021-01-01", periods=30, freq="15min", tz="UTC")
    train = pd.DataFrame({"x": np.arange(30.0)}, index=index)
    evaluation = train.iloc[:4].copy()
    evaluation.index += pd.Timedelta(days=365)
    data = ExperimentData(
        {},
        train,
        pd.Series(np.resize([-0.02, 0, 0.02], 30), index=index),
        evaluation,
        pd.Series([np.nan, -0.02, 0, 0.02], index=evaluation.index),
        evaluation,
        evaluation,
    )
    fit = XGBClassifier.fit

    def spy(self, x, y, **kwargs):
        assert x.index.equals(train.index) and "eval_set" not in kwargs
        return fit(self, x, y, **kwargs)

    monkeypatch.setattr(XGBClassifier, "fit", spy)
    _, pred, report = fit_predict(data, ModelConfig(threshold=0.01, n_estimators=3))
    assert pred.index.equals(evaluation.index)
    assert report["scored_rows"] == 3 and report["predictions_without_complete_outcome"] == 1
    _, again, _ = fit_predict(
        replace(data, validation_returns=data.validation_returns.fillna(999)),
        ModelConfig(threshold=0.01, n_estimators=3),
    )
    pd.testing.assert_frame_equal(pred, again)


def test_four_hour_hold_and_gate_override():
    index = pd.date_range("2022-01-01", periods=19, freq="15min", tz="UTC")
    pred = pd.DataFrame({"p_down": 0.8, "p_neutral": 0.1, "p_up": 0.1}, index=index)
    pred.iloc[0] = [0.1, 0.1, 0.8]
    gate = pd.Series(True, index=index)
    assert gated_targets(index, pred, gate, 240).tolist() == [1] * 16 + [0] * 3
    gate.iloc[5] = False
    assert gated_targets(index, pred, gate, 240).tolist() == [1] * 5 + [0] * 14
