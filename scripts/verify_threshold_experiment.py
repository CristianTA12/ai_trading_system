"""Independently replay policies, metrics and decisions for iteration 14 artifacts."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.diagnose_2023h1 import class_counts, replay
from src.backtesting.engine import BacktestResult
from src.backtesting.evaluator import FOLDS, SEEDS, SeedInput, evaluate_all, verdict_to_dict
from src.backtesting.policies import policy_metrics
from src.training.regression_experiment import fold_result


def verify(output):
    recipe = json.loads((output / "protocol.json").read_text())
    source = Path(recipe["source_experiment"])
    for name, digest in recipe["source_sha256"].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
    assert not recipe["test_evaluated"] and not recipe["validation_2024_evaluated"]
    gate = pd.read_parquet(output / "regime.parquet").allow_long
    labels = pd.read_parquet(output / "four_hour_labels.parquet")
    table = pd.read_csv(output / "comparison.csv")
    assert len(table) == 128
    assert len(list(output.glob("seed_*/*/model_*/model.ubj"))) == 40
    candidate, control = recipe["candidate"], recipe["control"]
    inputs = {arm: [] for arm in (candidate, control)}
    reads, missing = 0, 0

    def read(folder, seed, fold, arm, scenario, exposure):
        nonlocal reads
        eq, fills, trades = (
            pd.read_parquet(folder / f"{n}.parquet") for n in ("equity", "fills", "trades")
        )
        metrics = policy_metrics(BacktestResult(eq, fills, trades, exposure))
        row = table.loc[
            table.fold.eq(fold)
            & table.arm.eq(arm)
            & table.scenario.eq(scenario)
            & (table.seed.isna() if seed is None else table.seed.eq(seed))
        ]
        assert len(row) == 1
        for key, value in metrics.items():
            actual = row.iloc[0][key]
            if value is None:
                assert pd.isna(actual)
            else:
                np.testing.assert_allclose(actual, value, rtol=1e-12, atol=1e-12)
        if arm == control:
            original = source / f"seed_{seed}" / fold / "four_hour_regime" / scenario
            for name, frame in (("equity", eq), ("fills", fills), ("trades", trades)):
                pd.testing.assert_frame_equal(
                    frame, pd.read_parquet(original / f"{name}.parquet"), check_exact=True
                )
        reads += 1
        return fold_result(fold, BacktestResult(eq, fills, trades, exposure), metrics)

    benchmarks = {}
    for fold in FOLDS:
        for arm, exposure in (("buy_hold", 1.0), ("cash", 0.0)):
            fr = read(
                output / "benchmarks" / fold / arm / "base", None, fold, arm, "base", exposure
            )
            if arm == "buy_hold":
                benchmarks[fold] = fr
    for seed in SEEDS:
        results = {arm: {s: {} for s in ("base", "stress")} for arm in inputs}
        for fold in FOLDS:
            folder = output / f"seed_{seed}" / fold
            train = pd.read_parquet(output / "folds" / fold / "train_rows.parquet")
            p75 = pd.read_parquet(folder / "model_75/predictions.parquet")
            p100 = pd.read_parquet(folder / "model_100/predictions.parquet")
            pd.testing.assert_index_equal(p75.index, p100.index)
            np.testing.assert_array_equal(p75.actual_return, p100.actual_return)
            for arm, model_name, pred, threshold in (
                (candidate, "model_75", p75, 0.0075),
                (control, "model_100", p100, 0.01),
            ):
                diagnostics = json.loads((folder / model_name / "classification.json").read_text())
                assert diagnostics["config"]["threshold"] == threshold
                assert diagnostics["config"]["seed"] == seed
                assert diagnostics["train_class_counts"] == class_counts(train.return_4h, threshold)
                assert diagnostics["validation_class_counts"] == class_counts(
                    pred.actual_return, threshold
                )
                np.testing.assert_array_equal(
                    pred.actual_return, labels.target_return.reindex(pred.index)
                )
                assert (pred.label_end == pred.index + pd.Timedelta(hours=4)).all()
                missing += int(pred.actual_return.isna().sum())
                probs = pred[["p_down", "p_neutral", "p_up"]]
                signal = pd.Series(
                    (probs.to_numpy().argmax(axis=1) == 2) & pred.p_up.ge(0.5), index=pred.index
                )
                targets = pd.read_parquet(folder / arm / "targets.parquet").target_position
                expected, entries, _ = replay(targets.index, signal, gate)
                np.testing.assert_array_equal(targets, expected)
                trades = pd.read_parquet(folder / arm / "base/trades.parquet")
                assert entries == trades.entry_time.tolist()
                for scenario in ("gross", "base", "stress"):
                    fr = read(
                        folder / arm / scenario, seed, fold, arm, scenario, float(targets.mean())
                    )
                    pd.testing.assert_index_equal(
                        fr.equity_curve.index, benchmarks[fold].equity_curve.index
                    )
                    if scenario != "gross":
                        results[arm][scenario][fold] = fr
        for arm in inputs:
            inputs[arm].append(
                SeedInput(seed, results[arm]["base"], results[arm]["stress"], benchmarks)
            )
    decisions = {}
    for arm in inputs:
        verdict = verdict_to_dict(evaluate_all(inputs[arm]))
        assert verdict == json.loads((output / f"{arm}_verdict.json").read_text())
        if arm == control:
            assert verdict == json.loads((source / "four_hour_regime_verdict.json").read_text())
        decisions[arm] = {"passes": verdict["passes"], "seeds_passing": verdict["seeds_passing"]}
    assert reads == 128 and missing == 150
    return {
        "verified": True,
        "backtests": reads,
        "models": 40,
        "control_exactly_reproduced": True,
        "paired_prediction_rows": True,
        "independent_policy_replay": True,
        "unscorable_predictions_retained": missing,
        "decision": decisions,
        "test_evaluated": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.output), indent=2))
