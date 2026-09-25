from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from src.backtesting.dataset import ExperimentData
from src.backtesting.diagnostics import classification_diagnostics, sensitivity
from src.backtesting.engine import ExecutionConfig
from src.models.xgboost.classifier import position_targets
from src.training.walk_forward import FOLD_BOUNDARIES, training_folds


def probabilities(values):
    return pd.DataFrame(
        values,
        columns=["p_down", "p_neutral", "p_up"],
        index=pd.date_range("2024-01-01", periods=len(values), freq="15min", tz="UTC"),
    )


def test_lower_confidence_preserves_up_argmax_and_tie_policy():
    predictions = probabilities(
        [[0.1, 0.5, 0.4], [0.31, 0.29, 0.4], [0.4, 0.2, 0.4], [0.2, 0.2, 0.6]]
    )
    assert position_targets(predictions, 0.35).tolist() == [0, 1, 0, 1]
    assert position_targets(predictions, 0.50).tolist() == [0, 0, 0, 1]
    with pytest.raises(ValueError):
        position_targets(predictions * 2, 0.35)


def test_cost_sensitivity_recomputes_capital_and_holding_times():
    predictions = probabilities(
        [[0.1, 0.1, 0.8], [0.1, 0.1, 0.8], [0.1, 0.8, 0.1], [0.1, 0.1, 0.8], [0.1, 0.8, 0.1]]
    )
    bars = pd.DataFrame(
        {name: [100, 100, 100, 100, 100] for name in ("open", "close", "high", "low")},
        index=predictions.index,
    )
    table, _ = sensitivity(bars, predictions, ExecutionConfig(taker_fee=0.01, slippage=0.02))
    gross = table[(table.confidence == 0.5) & (table.scenario == "gross")].iloc[0]
    net = table[(table.confidence == 0.5) & (table.scenario == "net")].iloc[0]
    fees = table[(table.confidence == 0.5) & (table.scenario == "fees_only")].iloc[0]
    assert gross.total_return == 0
    assert fees.total_return == pytest.approx((0.99 / 1.01) ** 2 - 1)
    assert net.total_return == pytest.approx((0.98 * 0.99 / (1.02 * 1.01)) ** 2 - 1)
    assert net.mean_hold_minutes == 22.5
    assert net.one_bar_trade_fraction == 0.5
    assert net.exposure == 0.6


def test_three_class_reference_and_directional_abstentions():
    predictions = probabilities([[0.8, 0.1, 0.1], [0.1, 0.8, 0.1], [0.1, 0.8, 0.1]])
    returns = pd.Series([-0.004, 0, 0.004], index=predictions.index)
    report = classification_diagnostics(predictions, returns, 0.0025)
    assert report["balanced_accuracy"] == pytest.approx(2 / 3)
    assert report["random_balanced_accuracy_reference"] == pytest.approx(1 / 3)
    assert report["recall_by_class"] == {"DOWN": 1, "NEUTRAL": 1, "UP": 0}
    assert report["directional_accuracy_including_neutral_abstentions"] == 0.5


def test_walk_forward_purges_boundaries_and_excludes_outer_validation():
    index = pd.date_range("2020-01-01", "2023-12-31", freq="1D", tz="UTC")
    edges = pd.DatetimeIndex(
        [pd.Timestamp(cut, tz="UTC") - pd.Timedelta(minutes=15) for cut in FOLD_BOUNDARIES]
    )
    index = index.union(edges)
    features = pd.DataFrame({"feature": np.arange(len(index))}, index=index)
    returns = pd.Series(0.004, index=index)
    bars = pd.DataFrame({"open": 100, "close": 101}, index=index)
    poison = pd.DataFrame(
        {"feature": [999999]}, index=pd.DatetimeIndex([pd.Timestamp("2024-01-01", tz="UTC")])
    )
    data = ExperimentData(
        {"train_end": "2024-01-01"},
        features,
        returns,
        poison,
        pd.Series(999, index=poison.index),
        poison,
        poison,
        bars,
    )
    folds = list(training_folds(data))
    assert len(folds) == 4
    for (name, fold), stop_text in zip(folds, FOLD_BOUNDARIES[1:], strict=True):
        start, stop = pd.Timestamp(name, tz="UTC"), pd.Timestamp(stop_text, tz="UTC")
        assert (fold.train_features.index + pd.Timedelta(minutes=15) < start).all()
        assert (fold.validation_features.index >= start).all()
        assert (fold.validation_features.index + pd.Timedelta(minutes=15) < stop).all()
        assert fold.validation_features.feature.max() < 999999
        assert fold.validation_bars.index.max() < stop
    with pytest.raises(ValueError, match="invadiría"):
        list(training_folds(replace(data, metadata={"train_end": "2023-12-01"})))
