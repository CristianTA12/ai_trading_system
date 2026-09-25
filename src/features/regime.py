"""Preregistered v2 additions: 30-day drawdown, lag context and daily efficiency."""

import numpy as np
import pandas as pd

from src.backtesting.engine import STEP, validate_index

PEAK_WINDOW = 2880
TREND_WINDOW = 96
NEW_COLUMNS = [
    "drawdown_from_peak_2880",
    "return_1_lag_1",
    "return_1_lag_4",
    "rsi_14_cutler_lag_1",
    "trend_strength_96",
]


def build_regime_features(bars: pd.DataFrame, base_features: pd.DataFrame) -> pd.DataFrame:
    """Preserve v1 columns exactly, reset all new windows/lags at each gap.

    The output is timestamped at bar close, so the newly closed high is observable.
    Missing warmup rows are dropped, never filled or interpolated.
    """
    validate_index(bars.index)
    validate_index(base_features.index)
    if bars.empty or (bars.index != bars.index.floor("15min")).any():
        raise ValueError("Se requieren velas de 15m no vacías")
    if (
        not np.isfinite(bars[["close", "high"]].to_numpy()).all()
        or (bars.close <= 0).any()
        or (bars.high < bars.close).any()
    ):
        raise ValueError("Precios inválidos para drawdown/tendencia")
    if set(NEW_COLUMNS) & set(base_features.columns):
        raise ValueError("Las features base ya contienen columnas v2")
    groups = bars.index.to_series().diff().ne(STEP).cumsum()
    frames = []
    for _, segment in bars.groupby(groups):
        available = segment.index + STEP
        base = base_features.reindex(available)
        additions = pd.DataFrame(index=available)
        additions[NEW_COLUMNS[0]] = (
            segment.close / segment.high.rolling(PEAK_WINDOW, min_periods=PEAK_WINDOW).max() - 1
        ).to_numpy()
        additions[NEW_COLUMNS[1]] = base.return_1.shift(1)
        additions[NEW_COLUMNS[2]] = base.return_1.shift(4)
        additions[NEW_COLUMNS[3]] = base.rsi_14_cutler.shift(1)
        path = segment.close.diff().abs().rolling(TREND_WINDOW, min_periods=TREND_WINDOW).sum()
        efficiency = ((segment.close - segment.close.shift(TREND_WINDOW)) / path).where(
            path != 0, 0
        )
        additions[NEW_COLUMNS[4]] = efficiency.clip(-1, 1).to_numpy()
        frames.append(base.join(additions).replace([np.inf, -np.inf], np.nan).dropna())
    result = pd.concat(frames)
    result.index.name = base_features.index.name
    return result
