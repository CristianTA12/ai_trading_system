"""Fixed weekly momentum, updated after daily UTC close; no fitted parameters."""

import numpy as np
import pandas as pd

from src.backtesting.engine import validate_index


def daily_momentum(bars: pd.DataFrame, decisions: pd.DatetimeIndex) -> pd.DataFrame:
    validate_index(bars.index)
    validate_index(decisions)
    if bars.empty or not np.isfinite(bars.close).all() or (bars.close <= 0).any():
        raise ValueError("Positive finite closes required")
    if (bars.index != bars.index.floor("15min")).any():
        raise ValueError("15 minute grid required")
    days = pd.date_range(bars.index.min().floor("D"), bars.index.max().floor("D"), freq="D")
    closes = bars.close.reindex(days + pd.Timedelta(hours=23, minutes=45))
    closes.index = days
    valid = closes.rolling(8, min_periods=8).count().eq(8)
    daily = pd.DataFrame({"available_at": days + pd.Timedelta(days=1)})
    daily["momentum_7d"] = (closes / closes.shift(7) - 1).where(valid).to_numpy()
    result = pd.merge_asof(
        pd.DataFrame({"decision_at": decisions}),
        daily,
        left_on="decision_at",
        right_on="available_at",
        allow_exact_matches=False,
        direction="backward",
        tolerance=pd.Timedelta(days=1),
    ).set_index("decision_at")
    result.index.name = decisions.name
    result["valid"] = result.momentum_7d.notna()
    result["target_position"] = result.momentum_7d.gt(0).astype(int)
    return result
