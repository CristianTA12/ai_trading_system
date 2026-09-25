"""Fixed sensitivity checks: vary execution rules, never select on validation."""

from dataclasses import replace

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from src.backtesting.engine import ExecutionConfig, run_backtest
from src.backtesting.metrics import compute_metrics
from src.models.xgboost.classifier import encode_classes, position_targets

CONFIDENCES = (0.35, 0.40, 0.50)


def classification_diagnostics(
    predictions: pd.DataFrame, returns: pd.Series, threshold: float
) -> dict:
    if not predictions.index.equals(returns.index):
        raise ValueError("Predicciones y retornos deben estar alineados")
    actual = encode_classes(returns, threshold)
    predicted = predictions[["p_down", "p_neutral", "p_up"]].to_numpy().argmax(axis=1)
    matrix = confusion_matrix(actual, predicted, labels=[0, 1, 2])
    counts = matrix.sum(axis=1)
    recalls = np.divide(matrix.diagonal(), counts, out=np.zeros(3, dtype=float), where=counts > 0)
    # Directional accuracy is reported only where the true outcome is non-neutral;
    # predicting neutral counts as incorrect rather than silently discarding abstentions.
    directional = actual != 1
    table = pd.DataFrame(
        {"p_up": predictions.p_up, "actual_up": actual == 2, "realized_bps": returns * 10_000}
    )
    table["bin"] = pd.cut(
        table.p_up, [0, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.8, 1], include_lowest=True
    )
    buckets = table.groupby("bin", observed=True).agg(
        count=("p_up", "size"),
        mean_p_up=("p_up", "mean"),
        observed_up_rate=("actual_up", "mean"),
        mean_next_bar_bps=("realized_bps", "mean"),
    )
    buckets.index = buckets.index.astype(str)
    return {
        "random_balanced_accuracy_reference": 1 / 3,
        "balanced_accuracy": float(recalls.mean()) if (counts > 0).all() else None,
        "recall_by_class": dict(zip(("DOWN", "NEUTRAL", "UP"), recalls.tolist(), strict=True)),
        "confusion_matrix": matrix.tolist(),
        "directional_accuracy_including_neutral_abstentions": (
            float(np.mean(predicted[directional] == actual[directional]))
            if directional.any()
            else None
        ),
        "probability_buckets": buckets.to_dict(orient="index"),
        "up_argmax_fraction": float(np.mean(predicted == 2)),
        "interpretation": "Class weights affect probability calibration; 1/3 is a chance reference, not a significance test.",
    }


def sensitivity(
    bars: pd.DataFrame, predictions: pd.DataFrame, execution: ExecutionConfig
) -> tuple[pd.DataFrame, dict]:
    """Same signals/prices for gross, fee-only and full-cost counterfactuals.

    Each scenario recomputes position sizes from its own cash balance: return differences
    include compounding and cannot be calculated by adding paid fees back to net return.
    """
    rows, results = [], {}
    for confidence in CONFIDENCES:
        targets = position_targets(predictions, confidence)
        scenarios = {
            "gross": replace(execution, maker_fee=0, taker_fee=0, slippage=0),
            "fees_only": replace(execution, slippage=0),
            "net": execution,
        }
        for name, config in scenarios.items():
            result = run_backtest(bars, targets, config)
            trades = result.trades
            durations = (
                (trades.exit_time - trades.entry_time).dt.total_seconds() / 60
                if len(trades)
                else pd.Series(dtype=float)
            )
            trade_bps = (
                trades.net_pnl / trades.entry_cost * 10_000
                if len(trades)
                else pd.Series(dtype=float)
            )
            metrics = compute_metrics(result)
            metrics.update(
                {
                    "confidence": confidence,
                    "scenario": name,
                    "mean_hold_minutes": float(durations.mean()) if len(durations) else None,
                    "median_hold_minutes": float(durations.median()) if len(durations) else None,
                    "one_bar_trade_fraction": (
                        float((durations == 15).mean()) if len(durations) else None
                    ),
                    "mean_trade_bps": float(trade_bps.mean()) if len(trade_bps) else None,
                    "median_trade_bps": float(trade_bps.median()) if len(trade_bps) else None,
                    "signals_up": int(targets.sum()),
                }
            )
            rows.append(metrics)
            if name == "net":
                results[f"p_up_{confidence:.2f}"] = result
    return pd.DataFrame(rows), results
