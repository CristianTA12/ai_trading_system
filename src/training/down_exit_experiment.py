"""Iteration 16: zero new models, isolated DOWN exit policy on frozen SP500 predictions."""

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, replace
from importlib.metadata import version
from pathlib import Path

import click
import pandas as pd
from xgboost import XGBClassifier

from scripts.verify_sp500_experiment import verify as verify_source
from src.backtesting.dataset import load_dataset
from src.backtesting.engine import ExecutionConfig, run_backtest
from src.backtesting.evaluator import (
    FOLDS,
    SEEDS,
    SeedInput,
    _concatenate_equity,
    criterion_sha256,
    evaluate_all,
    save_verdict,
)
from src.backtesting.experiment import track_results, write_json
from src.backtesting.policies import policy_metrics
from src.backtesting.regime_gate import daily_regime, gated_down_exit_targets, gated_targets
from src.models.xgboost.four_hour import four_hour_labels, paired_horizon_folds
from src.training.four_hour_experiment import DATASET, ROOT
from src.training.regression_experiment import fold_result, plot_curves, save_result
from src.training.sp500_experiment import (
    assert_control_predictions,
    assert_control_result,
    augment_window,
)

PREREGISTRATION = "7d4d106"
SOURCE = ROOT / "data/experiments/iteration-15-20261007-sp500"
CANDIDATE, CONTROL = "sp500_exit_down", "sp500_baseline"
CRITERION = "12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a"


def source_integrity():
    manifest = json.loads((SOURCE / "final_manifest.json").read_text())
    for name, digest in manifest["files_sha256"].items():
        assert hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == digest, name
    return manifest


def run_iteration(output, tracking_uri):
    docs = ["docs/iteration-16-protocol.md", "docs/risk-return-v1.yaml"]
    if subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--",
            "src",
            "scripts",
            "tests",
            *docs,
        ],
        cwd=ROOT,
    ).strip():
        raise ValueError("Commit implementation before evaluation")
    subprocess.check_call(
        ["git", "ls-files", "--error-unmatch", str(Path(__file__).relative_to(ROOT))],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
    )
    for name in docs:
        frozen = subprocess.check_output(["git", "show", f"{PREREGISTRATION}:{name}"], cwd=ROOT)
        assert frozen.replace(b"\r\n", b"\n") == (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
    assert criterion_sha256() == CRITERION
    assert (
        hashlib.sha256((DATASET / "metadata.json").read_bytes()).hexdigest()
        == "a6a80da91f7956a49b5641038ae047b5422fba800a60fa1c7df23c7fd2b42c35"
    )
    manifest = source_integrity()
    manifest_hash = hashlib.sha256((SOURCE / "final_manifest.json").read_bytes()).hexdigest()
    click.echo("Verifying immutable iteration 15 artifacts")
    verified = verify_source(SOURCE)
    recipe = json.loads((SOURCE / "protocol.json").read_text())
    for library, recorded in recipe["libraries"].items():
        assert version(library) == recorded, library
    data = load_dataset(DATASET, train_only=True)
    labels = four_hour_labels(data.train_bars, data.train_features.index)
    gate = daily_regime(data.train_bars, data.train_bars.index)
    pd.testing.assert_frame_equal(
        labels, pd.read_parquet(SOURCE / "four_hour_labels.parquet"), check_exact=True
    )
    pd.testing.assert_frame_equal(
        gate, pd.read_parquet(SOURCE / "regime.parquet"), check_exact=True
    )
    folds = list(paired_horizon_folds(data, labels))
    windows, predictions = {}, {}
    for name, (_, short, window) in zip(FOLDS, folds, strict=True):
        train = pd.DataFrame(
            {
                "return_15m": short.train_returns,
                "return_4h": window.train_returns,
                "label_end_4h": window.train_features.index + pd.Timedelta(hours=4),
            }
        )
        pd.testing.assert_frame_equal(
            train, pd.read_parquet(SOURCE / "folds" / name / "train_rows.parquet"), check_exact=True
        )
        augmented = augment_window(window, SOURCE / "macro_features" / "alignment" / name)
        windows[name] = window
        for seed in SEEDS:
            folder = SOURCE / f"seed_{seed}" / name / "model_sp500"
            pred = pd.read_parquet(folder / "predictions.parquet")
            model = XGBClassifier()
            model.load_model(folder / "model.ubj")
            assert_control_predictions(model, augmented, pred)
            predictions[seed, name] = pred
    click.echo("All 20 frozen model probabilities reproduced exactly")
    output.mkdir(parents=True, exist_ok=False)
    for name in docs:
        shutil.copyfile(ROOT / name, output / Path(name).name)
    for name in ("four_hour_labels.parquet", "regime.parquet", "coverage.csv"):
        shutil.copyfile(SOURCE / name, output / name)
    shutil.copytree(SOURCE / "folds", output / "folds")
    config = ExecutionConfig()
    scenarios = {
        "gross": replace(config, taker_fee=0, maker_fee=0, slippage=0),
        "base": config,
        "stress": replace(config, slippage=0.0002),
    }
    write_json(
        output / "protocol.json",
        {
            "preregistration_commit": PREREGISTRATION,
            "git_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "candidate": CANDIDATE,
            "control": CONTROL,
            "source_experiment": str(SOURCE),
            "source_sha256": manifest["files_sha256"],
            "source_manifest_sha256": manifest_hash,
            "source_verification": verified,
            "criterion_sha256": CRITERION,
            "seeds": SEEDS,
            "folds": FOLDS,
            "libraries": recipe["libraries"],
            "execution": {k: asdict(v) for k, v in scenarios.items()},
            "minimum_hold_minutes": 240,
            "entry_confidence": 0.5,
            "exit": "DOWN_argmax",
            "conditional_research": True,
            "historical_availability_proven": False,
            "test_evaluated": False,
            "validation_2024_evaluated": False,
            "code_sha256": {
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT / "src").rglob("*.py"))
            },
        },
    )
    rows, logged, benchmarks = [], {}, {}
    results = {
        arm: {seed: {s: {} for s in scenarios} for seed in SEEDS} for arm in (CONTROL, CANDIDATE)
    }

    def evaluate(folder, bars, targets, seed, fold, arm, scenario):
        result = run_backtest(bars, targets, scenarios[scenario])
        if arm == CONTROL:
            assert_control_result(
                result, SOURCE / f"seed_{seed}" / fold / "sp500_regime" / scenario
            )
        metrics = policy_metrics(result)
        save_result(folder, result)
        rows.append({"seed": seed, "fold": fold, "arm": arm, "scenario": scenario, **metrics})
        logged[f"{seed}.{fold}.{arm}.{scenario}"] = {
            k: metrics[k] for k in ("total_return", "sharpe", "max_drawdown", "trades", "exposure")
        }
        return fold_result(fold, result, metrics)

    for fold in FOLDS:
        bars = windows[fold].validation_bars
        for arm, position in (("buy_hold", 1), ("cash", 0)):
            fr = evaluate(
                output / "benchmarks" / fold / arm / "base",
                bars,
                pd.Series(position, index=bars.index),
                None,
                fold,
                arm,
                "base",
            )
            if arm == "buy_hold":
                benchmarks[fold] = fr
    # All controls finish before the first candidate, with no additional control simulations.
    for arm, policy in ((CONTROL, gated_targets), (CANDIDATE, gated_down_exit_targets)):
        for seed in SEEDS:
            for fold in FOLDS:
                bars = windows[fold].validation_bars
                fold_dir = output / f"seed_{seed}" / fold
                if arm == CONTROL:
                    shutil.copytree(
                        SOURCE / f"seed_{seed}" / fold / "model_sp500", fold_dir / "model_sp500"
                    )
                targets = policy(bars.index, predictions[seed, fold], gate.allow_long, 240)
                if arm == CONTROL:
                    pd.testing.assert_frame_equal(
                        targets.to_frame(),
                        pd.read_parquet(
                            SOURCE / f"seed_{seed}" / fold / "sp500_regime" / "targets.parquet"
                        ),
                        check_exact=True,
                    )
                folder = fold_dir / arm
                folder.mkdir(parents=True)
                targets.to_frame().to_parquet(folder / "targets.parquet")
                for scenario in scenarios:
                    fr = evaluate(folder / scenario, bars, targets, seed, fold, arm, scenario)
                    results[arm][seed][scenario][fold] = fr
                    if scenario == "base":
                        click.echo(
                            f"{arm} seed={seed} {fold}: return={fr.net_return:.2%} DD={fr.max_drawdown:.2%} trades={fr.n_trades}"
                        )
            pd.DataFrame(rows).to_csv(output / "comparison.csv", index=False)
    decisions = {}
    for arm in (CONTROL, CANDIDATE):
        inputs = []
        for seed in SEEDS:
            r = results[arm][seed]
            inputs.append(SeedInput(seed, r["base"], r["stress"], benchmarks))
            curves = {
                s: _concatenate_equity([r[s][f].equity_curve for f in FOLDS]) for s in scenarios
            }
            for scenario, curve in curves.items():
                curve.to_frame("equity").to_parquet(
                    output / f"seed_{seed}" / f"{arm}_{scenario}_concatenated.parquet"
                )
            plot_curves(
                curves,
                output / f"seed_{seed}" / f"{arm}_concatenated.png",
                f"Iteration 16, {seed}, {arm}",
            )
        verdict = evaluate_all(inputs)
        save_verdict(verdict, output / f"{arm}_verdict.json")
        decisions[arm] = {"passes": verdict.passes, "seeds_passing": verdict.seeds_passing}
    assert json.loads((output / f"{CONTROL}_verdict.json").read_text()) == json.loads(
        (SOURCE / "sp500_regime_verdict.json").read_text()
    )
    source_integrity()
    assert (
        hashlib.sha256((SOURCE / "final_manifest.json").read_bytes()).hexdigest() == manifest_hash
    )
    report = {
        "decision": decisions,
        "models_trained": 0,
        "shared_models_reused": 20,
        "backtests": len(rows),
        "control_exactly_reproduced": True,
        "conditional_research": True,
        "historical_availability_proven": False,
        "test_evaluated": False,
        "validation_2024_evaluated": False,
        "promoted": False,
    }
    write_json(output / "report.json", report)
    if tracking_uri:
        track_results(
            output,
            logged,
            {
                "partition": "train_internal_walk_forward",
                "preregistration_commit": PREREGISTRATION,
                "models_trained": 0,
                "conditional_research": True,
                "historical_availability_proven": False,
                "test_evaluated": False,
            },
            tracking_uri,
            "spot-iteration-16-down-exit",
        )
    click.echo(str(report))


@click.command()
@click.option("--output", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--tracking-uri", default="http://localhost:5000")
def main(output, tracking_uri):
    run_iteration(output, tracking_uri)


if __name__ == "__main__":
    main()
