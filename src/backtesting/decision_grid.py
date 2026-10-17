"""Fixed 4h UTC decisions on frozen predictions, with immediate safety exits."""

import pandas as pd

from src.backtesting.engine import validate_index
from src.models.xgboost.classifier import position_targets


def grid_targets(index, predictions, gate):
    for timestamps in (index, predictions.index, gate.index):
        validate_index(timestamps)
    entries = position_targets(predictions, 0.5)
    if not gate.dropna().isin([True, False]).all():
        raise ValueError("Invalid gate")
    allowed = gate.reindex(index).fillna(False).astype(bool)
    available = index.isin(entries.index)
    aligned = entries.reindex(index, fill_value=0)
    holding = 0
    values = []
    for i, timestamp in enumerate(index):
        if not allowed.iloc[i] or not available[i]:
            holding = 0
        elif timestamp == timestamp.floor("4h"):
            holding = int(aligned.iloc[i])
        values.append(holding)
    return pd.Series(values, index=index, name="target_position")
