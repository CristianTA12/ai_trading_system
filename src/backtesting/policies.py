"""Causal stateful exit policies; execution and cash remain in the backtester."""

import pandas as pd

from src.backtesting.engine import BacktestResult, validate_index
from src.backtesting.metrics import compute_metrics
from src.models.xgboost.classifier import position_targets

EXIT_POLICIES = {
    "baseline": (0, False),
    "hold_60m": (60, False),
    "exit_down": (0, True),
    "hold_60m_exit_down": (60, True),
}


def stateful_targets(
    index: pd.DatetimeIndex, entries: pd.Series, exits: pd.Series, minimum_hold_minutes: int = 0
) -> pd.Series:
    """Hold by elapsed time, not row count; use only the current signal.

    Missing signals force flat at the next observed open, even inside the minimum
    hold. Final liquidation is handled by the engine. Early exit signals are not latched.
    """
    validate_index(index)
    validate_index(entries.index)
    validate_index(exits.index)
    if not entries.index.equals(exits.index) or minimum_hold_minutes < 0:
        raise ValueError("Se requieren señales alineadas y holding no negativo")
    if not entries.isin([0, 1]).all() or not exits.isin([0, 1]).all():
        raise ValueError("Entradas y salidas deben ser booleanas")
    available = index.isin(entries.index)
    enter = entries.reindex(index, fill_value=False).to_numpy(dtype=bool)
    leave = exits.reindex(index, fill_value=False).to_numpy(dtype=bool)
    holding, entered = False, None
    targets = []
    duration = pd.Timedelta(minutes=minimum_hold_minutes)
    for i, timestamp in enumerate(index):
        if not available[i]:
            holding = False
        elif holding:
            if timestamp - entered >= duration and leave[i]:
                holding = False
        elif enter[i]:
            holding, entered = True, timestamp
        targets.append(int(holding))
    return pd.Series(targets, index=index, name="target_position")


def multiclass_policies(
    index: pd.DatetimeIndex, predictions: pd.DataFrame, confidence: float = 0.5
) -> dict[str, pd.Series]:
    entries = position_targets(predictions, confidence).astype(bool)
    classes = predictions[["p_down", "p_neutral", "p_up"]].to_numpy().argmax(axis=1)
    down = pd.Series(classes == 0, index=predictions.index)
    return {
        name: stateful_targets(index, entries, down if down_only else ~entries, minutes)
        for name, (minutes, down_only) in EXIT_POLICIES.items()
    }


def policy_metrics(result: BacktestResult) -> dict:
    metrics = compute_metrics(result)
    trades = result.trades
    duration = (
        (trades.exit_time - trades.entry_time).dt.total_seconds() / 60
        if len(trades)
        else pd.Series(dtype=float)
    )
    bps = trades.net_pnl / trades.entry_cost * 10_000 if len(trades) else pd.Series(dtype=float)
    metrics.update(
        {
            "mean_hold_minutes": float(duration.mean()) if len(duration) else None,
            "median_hold_minutes": float(duration.median()) if len(duration) else None,
            "fraction_trades_under_60m": float((duration < 60).mean()) if len(duration) else None,
            "mean_trade_bps": float(bps.mean()) if len(bps) else None,
            "median_trade_bps": float(bps.median()) if len(bps) else None,
        }
    )
    return metrics
