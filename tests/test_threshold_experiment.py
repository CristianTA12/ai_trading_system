"""Exact frozen control checks must detect drift, even below numeric tolerances."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.models.xgboost.classifier import encode_classes
from src.training.threshold_experiment import assert_control_predictions, assert_control_result


def test_threshold_endpoints_and_changed_classes():
    values = pd.Series([-0.01, -0.0075, 0.0, 0.0075, 0.01])
    assert encode_classes(values, 0.0075).tolist() == [0, 1, 1, 1, 2]
    assert encode_classes(values, 0.01).tolist() == [1, 1, 1, 1, 1]


def test_control_prediction_check_keeps_nan_outcomes_and_rejects_probability_drift():
    index = pd.date_range("2023-01-01", periods=2, freq="15min", tz="UTC")
    probabilities = np.array([[0.2, 0.3, 0.5], [0.1, 0.8, 0.1]])
    window = SimpleNamespace(
        validation_features=pd.DataFrame({"x": [1, 2]}, index=index),
        validation_returns=pd.Series([0.01, np.nan], index=index),
    )
    pred = pd.DataFrame(probabilities.copy(), index=index, columns=["p_down", "p_neutral", "p_up"])
    pred["actual_return"] = window.validation_returns
    pred["label_end"] = index + pd.Timedelta(hours=4)
    model = SimpleNamespace(predict_proba=lambda _: probabilities)
    assert_control_predictions(model, window, pred)
    pred.loc[index[0], "p_up"] += 1e-10
    with pytest.raises(AssertionError):
        assert_control_predictions(model, window, pred)


@pytest.mark.parametrize("field", ["equity", "fills", "trades"])
def test_control_replay_rejects_even_small_changes(tmp_path, field):
    result = SimpleNamespace(
        **{name: pd.DataFrame({"value": [1.0]}) for name in ("equity", "fills", "trades")}
    )
    for name in ("equity", "fills", "trades"):
        getattr(result, name).to_parquet(tmp_path / f"{name}.parquet")
    assert_control_result(result, tmp_path)
    getattr(result, field).iloc[0, 0] += 1e-10
    with pytest.raises(AssertionError):
        assert_control_result(result, tmp_path)
