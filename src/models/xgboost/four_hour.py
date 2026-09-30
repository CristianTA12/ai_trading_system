"""Fixed 16-bar target and matched 15m comparison for iteration 13."""

from dataclasses import replace

import numpy as np
import pandas as pd

from src.backtesting.engine import STEP, validate_index
from src.training.walk_forward import training_folds

HORIZON = pd.Timedelta(hours=4)
THRESHOLD = 0.01


def four_hour_labels(bars: pd.DataFrame, feature_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Entry open(t), close of bar open(t+3h45m), label_end=t+4h.

    Require all sixteen consecutive execution bars; do not bridge future gaps.
    The index already is a decision/execution timestamp, not the prior bar open.
    """
    validate_index(bars.index)
    validate_index(feature_index)
    if (
        not np.isfinite(bars[["open", "close"]].to_numpy()).all()
        or (bars[["open", "close"]] <= 0).any().any()
    ):
        raise ValueError("Precios inválidos")
    times = bars.index.to_series()
    consecutive = pd.Series(True, index=bars.index)
    for offset in range(1, 16):
        consecutive &= times.shift(-offset).eq(times + offset * STEP)
    result = pd.DataFrame(
        {"target_return": bars.close.shift(-15) / bars.open - 1, "label_end": times + HORIZON},
        index=bars.index,
    )
    return result.loc[consecutive].reindex(feature_index).dropna()


def paired_horizon_folds(data, labels):
    """Same complete-case train and prediction grid; future gaps mask scoring only."""
    for name, original in training_folds(data, HORIZON):
        common = original.train_features.index.intersection(labels.index)
        if common.empty:
            raise ValueError("Train vacío para horizonte 4h")
        matched = replace(
            original,
            train_features=original.train_features.loc[common],
            train_returns=original.train_returns.loc[common],
        )
        four_hour = replace(
            matched,
            train_returns=labels.loc[common, "target_return"],
            validation_returns=labels.target_return.reindex(original.validation_features.index),
        )
        yield name, matched, four_hour
