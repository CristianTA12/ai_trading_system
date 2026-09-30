"""Verify iteration 12 ledgers, causal policy state and risk-return verdicts."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtesting.engine import STEP, BacktestResult
from src.backtesting.evaluator import FOLDS, SEEDS, SeedInput, evaluate_all, verdict_to_dict
from src.backtesting.policies import policy_metrics
from src.training.regression_experiment import fold_result


def verify(output: Path) -> dict:
    recipe = json.loads((output / "protocol.json").read_text())
    assert recipe["models_trained"] == 0
    assert not recipe["test_evaluated"] and not recipe["validation_2024_evaluated"]
    gate = pd.read_parquet(output / "regime.parquet")
    assert gate.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
    valid = gate.loc[gate.valid]
    assert (valid.daily_available_at < valid.index).all()
    assert ((valid.index - valid.daily_available_at) <= pd.Timedelta(days=1)).all()
    assert gate.allow_long.equals((gate.sma50 > gate.sma200) & gate.valid)
    table = pd.read_csv(output / "comparison.csv")
    assert len(table) == 140
    source = Path(recipe["source"])

    def read(folder, fold, seed, arm, scenario):
        eq, fills, trades = (
            pd.read_parquet(folder / f"{name}.parquet") for name in ("equity", "fills", "trades")
        )
        result = BacktestResult(eq, fills, trades, 0.0)
        metrics = policy_metrics(result)
        subset = table.loc[
            table.fold.eq(fold)
            & table.arm.eq(arm)
            & table.scenario.eq(scenario)
            & (table.seed.isna() if seed is None else table.seed.eq(seed))
        ]
        assert len(subset) == 1
        for metric in (
            "total_return",
            "max_drawdown",
            "sharpe",
            "trades",
            "fees_paid",
            "mean_trade_bps",
        ):
            actual, saved = metrics[metric], subset.iloc[0][metric]
            assert (actual is None and pd.isna(saved)) or np.isclose(
                actual, saved, rtol=1e-10, atol=1e-12
            )
        if arm in ("v1_regime", "regime_only"):
            permitted = gate.allow_long.reindex(eq.index - STEP, fill_value=False).to_numpy()
            assert not ((eq.quantity.to_numpy() > 0) & ~permitted).any()
        if arm == "v1_control":
            for name, frame in (("equity", eq), ("fills", fills), ("trades", trades)):
                pd.testing.assert_frame_equal(
                    frame,
                    pd.read_parquet(
                        source / f"seed_{seed}" / fold / "v1_matched" / scenario / f"{name}.parquet"
                    ),
                )
        return fold_result(fold, result, metrics)

    benchmarks = {}
    for fold in FOLDS:
        for arm in ("buy_hold", "cash", "regime_only"):
            for scenario in ("gross", "base", "stress") if arm == "regime_only" else ("base",):
                result = read(
                    output / "benchmarks" / fold / arm / scenario, fold, None, arm, scenario
                )
                if arm == "buy_hold":
                    benchmarks[fold] = result
    inputs = {arm: [] for arm in ("v1_control", "v1_regime")}
    for seed in SEEDS:
        results = {arm: {scenario: {} for scenario in ("base", "stress")} for arm in inputs}
        for fold in FOLDS:
            folder = output / f"seed_{seed}" / fold
            pred = pd.read_parquet(folder / "predictions.parquet")
            pd.testing.assert_frame_equal(
                pred,
                pd.read_parquet(source / f"seed_{seed}" / fold / "v1_matched/predictions.parquet"),
            )
            targets = pd.read_parquet(folder / "v1_regime/targets.parquet").target_position
            # Independent scalar policy replay; no call to gated_targets/stateful_targets.
            active, entry_at, expected = False, None, []
            probabilities = pred[["p_down", "p_neutral", "p_up"]]
            entries = pd.Series(
                (probabilities.to_numpy().argmax(axis=1) == 2) & (pred.p_up.to_numpy() >= 0.5),
                index=pred.index,
            )
            for t in targets.index:
                if not gate.at[t, "allow_long"] or t not in entries.index:
                    active = False
                elif active:
                    if t - entry_at >= pd.Timedelta(hours=1) and not entries.at[t]:
                        active = False
                elif entries.at[t]:
                    active, entry_at = True, t
                expected.append(int(active))
            np.testing.assert_array_equal(targets.to_numpy(), expected)
            for arm in inputs:
                for scenario in ("gross", "base", "stress"):
                    result = read(folder / arm / scenario, fold, seed, arm, scenario)
                    assert result.equity_curve.index.equals(benchmarks[fold].equity_curve.index)
                    if scenario != "gross":
                        results[arm][scenario][fold] = result
        for arm in inputs:
            inputs[arm].append(
                SeedInput(seed, results[arm]["base"], results[arm]["stress"], benchmarks)
            )
    decisions = {}
    for arm, values in inputs.items():
        verdict = verdict_to_dict(evaluate_all(values))
        assert verdict == json.loads((output / f"{arm}_verdict.json").read_text())
        decisions[arm] = {"passes": verdict["passes"], "seeds_passing": verdict["seeds_passing"]}
    return {
        "verified": True,
        "backtests": len(table),
        "models_trained": 0,
        "independent_policy_replay": True,
        "control_ledgers_identical": True,
        "decision": decisions,
        "test_evaluated": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.output), indent=2))
