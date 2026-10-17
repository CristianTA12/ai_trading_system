"""Iteration 18: reproduce all controls before one frozen decision-grid candidate."""

import argparse
import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from src.backtesting.dataset import load_dataset
from src.backtesting.decision_grid import grid_targets
from src.backtesting.engine import ExecutionConfig, run_backtest
from src.backtesting.evaluator import (
    FOLDS,
    SEEDS,
    SeedInput,
    criterion_sha256,
    evaluate_all,
    save_verdict,
)
from src.backtesting.experiment import track_results, write_json
from src.backtesting.policies import policy_metrics
from src.backtesting.regime_gate import gated_targets
from src.training.four_hour_experiment import DATASET, ROOT
from src.training.regression_experiment import fold_result, save_result

SOURCE = ROOT / "data/experiments/iteration-13-20260930-four-hour"
PREREG = "cd34886"
CONTROL, CANDIDATE = "four_hour_regime", "four_hour_grid"
CRITERION = "12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a"


def oracle(index, p, gate):
    """Independent state reconstruction: latest grid after latest forced flat."""
    expected, last_decision, last_flat = [], None, None
    for t in index:
        if t not in gate.index or pd.isna(gate.at[t]) or not gate.at[t] or t not in p.index:
            last_flat = t
        elif t.hour % 4 == 0 and t.minute == 0:
            last_decision = t
        if last_decision is None or (last_flat is not None and last_flat >= last_decision):
            expected.append(0)
        else:
            v = p.loc[last_decision, ["p_down", "p_neutral", "p_up"]].to_numpy()
            expected.append(int(v.argmax() == 2 and v[2] >= 0.5))
    return pd.Series(expected, index=index, name="target_position")


def run(output, tracking_uri):
    if subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            "src",
            "scripts",
            "tests",
            "docs/iteration-18-protocol.md",
        ],
        cwd=ROOT,
    ).strip():
        raise ValueError("Commit implementation before evaluation")
    document = ROOT / "docs/iteration-18-protocol.md"
    frozen = subprocess.check_output(
        ["git", "show", f"{PREREG}:docs/iteration-18-protocol.md"], cwd=ROOT
    )
    assert frozen.replace(b"\r\n", b"\n") == document.read_bytes().replace(b"\r\n", b"\n")
    assert criterion_sha256() == CRITERION
    source_recipe = json.loads((SOURCE / "protocol.json").read_text())
    assert not source_recipe["test_evaluated"] and not source_recipe["validation_2024_evaluated"]
    assert (
        hashlib.sha256((DATASET / "metadata.json").read_bytes()).hexdigest()
        == "a6a80da91f7956a49b5641038ae047b5422fba800a60fa1c7df23c7fd2b42c35"
    )
    data = load_dataset(DATASET, train_only=True)
    hashes = {}

    def read(name):
        path = SOURCE / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[name] = digest
        if name in source_recipe["artifact_sha256"]:
            assert digest == source_recipe["artifact_sha256"][name]
        return pd.read_parquet(path)

    gate = read("regime.parquet").allow_long
    predictions, saved_targets, bars = {}, {}, {}
    for seed in SEEDS:
        for fold in FOLDS:
            root = f"seed_{seed}/{fold}"
            predictions[seed, fold] = read(f"{root}/four_hour/predictions.parquet")
            targets = read(f"{root}/{CONTROL}/targets.parquet").target_position
            assert targets.index.min() >= pd.Timestamp("2022-01-01", tz="UTC")
            assert targets.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
            saved_targets[seed, fold] = targets
            bars[fold] = data.train_bars.loc[targets.index]
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(document, output / document.name)
    shutil.copyfile(ROOT / "docs/risk-return-v1.yaml", output / "risk-return-v1.yaml")
    config = ExecutionConfig()
    configs = {
        "gross": replace(config, taker_fee=0, maker_fee=0, slippage=0),
        "base": config,
        "stress": replace(config, slippage=0.0002),
    }
    results = {
        arm: {seed: {s: {} for s in configs} for seed in SEEDS} for arm in (CONTROL, CANDIDATE)
    }
    rows, benchmarks = [], {}

    def evaluate(folder, fold, targets, seed, arm, scenario):
        result = run_backtest(bars[fold], targets, configs[scenario])
        if arm == CONTROL:
            for kind in ("equity", "fills", "trades"):
                original = read(f"seed_{seed}/{fold}/{CONTROL}/{scenario}/{kind}.parquet")
                pd.testing.assert_frame_equal(getattr(result, kind), original, check_exact=True)
        m = policy_metrics(result)
        save_result(folder, result)
        rows.append({"seed": seed, "fold": fold, "arm": arm, "scenario": scenario, **m})
        return fold_result(fold, result, m)

    for arm in (CONTROL, CANDIDATE):
        if arm == CANDIDATE:
            assert len(rows) == 60
            print("All 60 controls reproduced exactly; starting fixed candidate", flush=True)
        for seed in SEEDS:
            for fold in FOLDS:
                p = predictions[seed, fold]
                index = bars[fold].index
                if arm == CONTROL:
                    targets = gated_targets(index, p, gate, 240)
                    pd.testing.assert_series_equal(
                        targets, saved_targets[seed, fold], check_exact=True
                    )
                else:
                    targets = grid_targets(index, p, gate)
                    pd.testing.assert_series_equal(
                        targets, oracle(index, p, gate), check_exact=True
                    )
                destination = output / f"seed_{seed}" / fold / arm
                destination.mkdir(parents=True)
                targets.to_frame().to_parquet(destination / "targets.parquet")
                for scenario in configs:
                    fr = evaluate(destination / scenario, fold, targets, seed, arm, scenario)
                    results[arm][seed][scenario][fold] = fr
                print(f"{arm} {seed} {fold} complete", flush=True)
        pd.DataFrame(rows).to_csv(output / "comparison.csv", index=False)
    for fold in FOLDS:
        for arm, target in (("buy_hold", 1), ("cash", 0)):
            fr = evaluate(
                output / "benchmarks" / fold / arm / "base",
                fold,
                pd.Series(target, index=bars[fold].index),
                None,
                arm,
                "base",
            )
            if arm == "buy_hold":
                benchmarks[fold] = fr
                original = read(f"benchmarks/{fold}/buy_hold/base/equity.parquet").equity
                pd.testing.assert_series_equal(fr.equity_curve, original, check_exact=True)
    decisions = {}
    for arm in (CONTROL, CANDIDATE):
        verdict = evaluate_all(
            [
                SeedInput(
                    seed, results[arm][seed]["base"], results[arm][seed]["stress"], benchmarks
                )
                for seed in SEEDS
            ]
        )
        save_verdict(verdict, output / f"{arm}_verdict.json")
        decisions[arm] = {"passes": verdict.passes, "seeds_passing": verdict.seeds_passing}
    assert json.loads((output / f"{CONTROL}_verdict.json").read_text()) == json.loads(
        (SOURCE / f"{CONTROL}_verdict.json").read_text()
    )
    for name, digest in hashes.items():
        assert hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == digest
    pd.DataFrame(rows).to_csv(output / "comparison.csv", index=False)
    write_json(
        output / "protocol.json",
        {
            "preregistration_commit": PREREG,
            "git_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_sha256": hashes,
            "criterion_sha256": CRITERION,
            "execution": {k: asdict(v) for k, v in configs.items()},
            "test_evaluated": False,
            "validation_2024_evaluated": False,
        },
    )
    report = {
        "decision": decisions,
        "models_trained": 0,
        "backtests": len(rows),
        "control_exactly_reproduced": True,
        "candidate_targets_independently_verified": True,
        "test_evaluated": False,
        "validation_2024_evaluated": False,
        "promoted": False,
    }
    write_json(output / "report.json", report)
    if tracking_uri:
        track_results(
            output,
            {k: {"seeds_passing": v["seeds_passing"]} for k, v in decisions.items()},
            {
                "partition": "development_reused_folds",
                "models_trained": 0,
                "preregistration": PREREG,
            },
            tracking_uri,
            "spot-iteration-18-decision-grid",
        )
    write_json(
        output / "final_manifest.json",
        {
            "files_sha256": {
                str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(output.rglob("*"))
                if p.is_file()
            }
        },
    )
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tracking-uri", default="http://localhost:5000")
    args = parser.parse_args()
    run(args.output, args.tracking_uri)
