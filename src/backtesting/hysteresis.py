"""Frozen iteration-19 strong-DOWN exit on the original gated UP entries."""

import pandas as pd

from src.backtesting.engine import validate_index
from src.backtesting.policies import stateful_targets
from src.models.xgboost.classifier import position_targets


def hysteresis_targets(index, predictions, gate):
    """Force cash on missing inputs; otherwise hold 4h before strong DOWN exit."""
    validate_index(gate.index)
    if not gate.isin([True, False]).all():
        raise ValueError("Gate must be boolean without NaN")
    allowed = gate.reindex(predictions.index, fill_value=False).astype(bool)
    eligible = predictions.loc[allowed]
    entries = position_targets(eligible, 0.5).astype(bool)
    classes = eligible[["p_down", "p_neutral", "p_up"]].to_numpy().argmax(axis=1)
    exits = pd.Series(classes == 0, index=eligible.index) & eligible.p_down.ge(0.5)
    return stateful_targets(index, entries, exits, minimum_hold_minutes=240)
