"""Causal benchmark position targets, all expressed at execution time."""

import numpy as np
import pandas as pd


def benchmark_targets(bars: pd.DataFrame, features: pd.DataFrame, seed: int = 42) -> dict:
    # close/EMA20 < close/EMA50 iff EMA20 > EMA50, for positive prices.
    ema = (features.ema_distance_20 < features.ema_distance_50).astype(int)
    return {
        "buy_hold": pd.Series(1, index=bars.index),
        "ema_20_50": ema.reindex(bars.index, fill_value=0),
        "random": pd.Series(
            np.random.default_rng(seed).integers(0, 2, len(bars)), index=bars.index
        ),
    }
