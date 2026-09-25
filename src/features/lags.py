"""Three preregistered v1 lags, with no long-window regime indicators."""

import numpy as np
import pandas as pd

from src.backtesting.engine import STEP, validate_index

LAG_COLUMNS = ["return_1_lag_1", "return_1_lag_4", "rsi_14_cutler_lag_1"]


def build_lag_features(bars: pd.DataFrame, base_features: pd.DataFrame) -> pd.DataFrame:
    """Shift on the continuous bar clock, preserving all v1 values and gap resets."""
    validate_index(bars.index)
    validate_index(base_features.index)
    if bars.empty or (bars.index != bars.index.floor("15min")).any():
        raise ValueError("Se requieren velas de 15m no vacías")
    if set(LAG_COLUMNS) & set(base_features.columns):
        raise ValueError("Las columnas de lags ya existen en las features base")
    groups = bars.index.to_series().diff().ne(STEP).cumsum()
    frames = []
    for _, segment in bars.groupby(groups):
        base = base_features.reindex(segment.index + STEP)
        additions = pd.DataFrame(index=base.index)
        additions[LAG_COLUMNS[0]] = base.return_1.shift(1)
        additions[LAG_COLUMNS[1]] = base.return_1.shift(4)
        additions[LAG_COLUMNS[2]] = base.rsi_14_cutler.shift(1)
        frames.append(base.join(additions).replace([np.inf, -np.inf], np.nan).dropna())
    result = pd.concat(frames)
    result.index.name = base_features.index.name
    return result
