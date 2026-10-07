"""Fixed daily SMA50 > SMA200 gate, calculated solely from closed spot bars."""

import numpy as np
import pandas as pd

from src.backtesting.engine import validate_index
from src.backtesting.policies import stateful_targets
from src.models.xgboost.classifier import position_targets


def daily_regime(bars: pd.DataFrame, decisions: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily close is the close of the observed 23:45 UTC complete 15m bar.

    Missing daily endpoints stay NaN and invalidate rolling windows. Intraday
    gaps do not invalidate an observed daily close. At midnight the day's new
    value is not yet eligible: it first applies at 00:15 on our decision grid.
    """
    validate_index(bars.index)
    validate_index(decisions)
    if bars.empty or not np.isfinite(bars.close).all() or (bars.close <= 0).any():
        raise ValueError("Se requieren cierres positivos finitos")
    if (bars.index != bars.index.floor("15min")).any():
        raise ValueError("Barras fuera de rejilla 15m")
    calendar = pd.date_range(bars.index.min().floor("D"), bars.index.max().floor("D"), freq="D")
    endpoints = calendar + pd.Timedelta(hours=23, minutes=45)
    daily = pd.DataFrame({"daily_close": bars.close.reindex(endpoints).to_numpy()}, index=calendar)
    daily["sma50"] = daily.daily_close.rolling(50, min_periods=50).mean()
    daily["sma200"] = daily.daily_close.rolling(200, min_periods=200).mean()
    daily["daily_available_at"] = daily.index + pd.Timedelta(days=1)
    result = pd.merge_asof(
        pd.DataFrame({"decision_at": decisions}),
        daily.reset_index(drop=True),
        left_on="decision_at",
        right_on="daily_available_at",
        direction="backward",
        allow_exact_matches=False,
        tolerance=pd.Timedelta(days=1),
    ).set_index("decision_at")
    result.index.name = decisions.name
    result["valid"] = result[["sma50", "sma200"]].notna().all(axis=1)
    result["allow_long"] = result.valid & result.sma50.gt(result.sma200)
    return result


def gated_targets(
    index: pd.DatetimeIndex,
    predictions: pd.DataFrame,
    gate: pd.Series,
    minimum_hold_minutes: int = 60,
) -> pd.Series:
    """Recompute holding state; a closed/missing gate forces flat immediately.

    Do not multiply an ungated position series by the gate: reopening the gate
    requires a fresh eligible entry, never a latent position from the control.
    """
    validate_index(gate.index)
    if not gate.isin([True, False]).all():
        raise ValueError("El filtro debe ser booleano, sin NaN")
    allowed = gate.reindex(predictions.index, fill_value=False).astype(bool)
    entries = position_targets(predictions.loc[allowed], 0.5).astype(bool)
    return stateful_targets(index, entries, ~entries, minimum_hold_minutes=minimum_hold_minutes)


def gated_down_exit_targets(
    index: pd.DatetimeIndex,
    predictions: pd.DataFrame,
    gate: pd.Series,
    minimum_hold_minutes: int = 240,
) -> pd.Series:
    """Same UP entry and forced cash rules; after minimum hold, exit on DOWN only."""
    validate_index(gate.index)
    if not gate.isin([True, False]).all():
        raise ValueError("El filtro debe ser booleano, sin NaN")
    allowed = gate.reindex(predictions.index, fill_value=False).astype(bool)
    eligible = predictions.loc[allowed]
    entries = position_targets(eligible, 0.5).astype(bool)
    exits = pd.Series(
        eligible[["p_down", "p_neutral", "p_up"]].to_numpy().argmax(axis=1) == 0,
        index=eligible.index,
    )
    return stateful_targets(index, entries, exits, minimum_hold_minutes=minimum_hold_minutes)
