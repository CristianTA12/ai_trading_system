"""Iteration 12: replay frozen v1 predictions with a preregistered daily gate."""

import hashlib
import json
import subprocess
from dataclasses import asdict, replace
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import click
import numpy as np
import pandas as pd
from xgboost import XGBClassifier

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
    verdict_to_dict,
)
from src.backtesting.experiment import track_results, write_json
from src.backtesting.policies import multiclass_policies, policy_metrics
from src.backtesting.regime_gate import daily_regime, gated_targets
from src.training.regression_experiment import fold_result, plot_curves, save_result
from src.training.walk_forward import training_folds

ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = "8778570"
SOURCE = ROOT / "data/experiments/iteration-11-20260929-funding"
DATASET = ROOT / "data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z"
ARMS = ("v1_control", "v1_regime")


def verify_preregistration():
    paths = [
        "docs/iteration-12-protocol.md",
        "docs/iteration-12-inputs.json",
        "docs/risk-return-v1.yaml",
    ]
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--", "src", *paths], cwd=ROOT
    ).strip():
        raise ValueError("Registrar código y documentos antes de evaluar")
    for name in paths:
        registered = subprocess.check_output(["git", "show", f"{PREREGISTRATION}:{name}"], cwd=ROOT)
        if registered.replace(b"\r\n", b"\n") != (ROOT / name).read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError(f"Documento distinto al preregistro: {name}")
    manifest = json.loads((ROOT / paths[1]).read_text())
    for name, digest in manifest.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Input modificado: {name}")
    return paths


def run_iteration(output: Path, tracking_uri: str | None):
    documents = verify_preregistration()
    data = load_dataset(DATASET, train_only=True)
    if data.metadata["train_end"] != "2024-01-01":
        raise ValueError("Solo train hasta 2023")
    gate = daily_regime(data.train_bars, data.train_bars.index)
    folds = list(training_folds(data))
    output.mkdir(parents=True, exist_ok=False)
    for name in documents:
        (output / Path(name).name).write_bytes((ROOT / name).read_bytes())
    gate.to_parquet(output / "regime.parquet")
    execution = ExecutionConfig()
    scenarios = {
        "gross": replace(execution, taker_fee=0, maker_fee=0, slippage=0),
        "base": execution,
        "stress": replace(execution, slippage=0.0002),
    }
    write_json(
        output / "protocol.json",
        {
            "preregistration_commit": PREREGISTRATION,
            "git_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "criterion_sha256": criterion_sha256(),
            "source": str(SOURCE),
            "dataset_metadata": data.metadata,
            "seeds": SEEDS,
            "folds": FOLDS,
            "execution": {name: asdict(cfg) for name, cfg in scenarios.items()},
            "models_trained": 0,
            "validation_2024_evaluated": False,
            "test_evaluated": False,
            "rule": "daily SMA50 > SMA200; strict past availability; gate forces flat",
            "source_sha256": {
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT / "src").rglob("*.py"))
            },
            "libraries": {
                name: version(name) for name in ("xgboost", "pandas", "numpy", "mlflow", "pyarrow")
            },
        },
    )
    coverage = []
    for name, (_, window) in zip(FOLDS, folds, strict=True):
        g = gate.loc[window.validation_bars.index]
        coverage.append(
            {
                "fold": name,
                "bars": len(g),
                "valid_regime_fraction": float(g.valid.mean()),
                "gate_open_fraction": float(g.allow_long.mean()),
                "gate_switches": int(g.allow_long.astype(int).diff().abs().sum()),
            }
        )
    if any(row["valid_regime_fraction"] < 0.95 for row in coverage):
        raise ValueError("Cobertura régimen inferior al 95%")
    pd.DataFrame(coverage).to_csv(output / "coverage.csv", index=False)
    rows, benchmarks, logged = [], {}, {}

    def evaluate(folder, bars, targets, seed, fold, arm, scenario):
        result = run_backtest(bars, targets, scenarios[scenario])
        metrics = policy_metrics(result)
        save_result(folder, result)
        rows.append({"seed": seed, "fold": fold, "arm": arm, "scenario": scenario, **metrics})
        logged[f"{seed}.{fold}.{arm}.{scenario}"] = {
            key: metrics[key]
            for key in ("total_return", "max_drawdown", "sharpe", "trades", "exposure")
        }
        return fold_result(fold, result, metrics), result

    for name, (_, window) in zip(FOLDS, folds, strict=True):
        bars = window.validation_bars
        for arm, targets in (
            ("buy_hold", pd.Series(1, index=bars.index)),
            ("cash", pd.Series(0, index=bars.index)),
            ("regime_only", gate.loc[bars.index, "allow_long"].astype(int)),
        ):
            for scenario in scenarios if arm == "regime_only" else ("base",):
                fr, _ = evaluate(
                    output / "benchmarks" / name / arm / scenario,
                    bars,
                    targets,
                    None,
                    name,
                    arm,
                    scenario,
                )
                benchmarks[name, arm, scenario] = fr

    inputs = {arm: [] for arm in ARMS}
    for seed in SEEDS:
        results = {arm: {scenario: {} for scenario in scenarios} for arm in ARMS}
        for name, (_, window) in zip(FOLDS, folds, strict=True):
            source = SOURCE / f"seed_{seed}" / name / "v1_matched"
            predictions = pd.read_parquet(source / "predictions.parquet")
            if not predictions.index.equals(window.validation_features.index):
                raise ValueError("Predicciones fuera del fold preregistrado")
            np.testing.assert_array_equal(predictions.actual_return, window.validation_returns)
            model = XGBClassifier()
            model.load_model(source / "model.ubj")
            np.testing.assert_array_equal(
                model.predict_proba(window.validation_features),
                predictions[["p_down", "p_neutral", "p_up"]].to_numpy(),
            )
            bars = window.validation_bars
            targets = {
                "v1_control": multiclass_policies(bars.index, predictions)["hold_60m"],
                "v1_regime": gated_targets(bars.index, predictions, gate.allow_long),
            }
            pd.testing.assert_series_equal(
                targets["v1_control"], pd.read_parquet(source / "targets.parquet").target_position
            )
            fold_dir = output / f"seed_{seed}" / name
            fold_dir.mkdir(parents=True)
            predictions.to_parquet(fold_dir / "predictions.parquet")
            for arm in ARMS:
                folder = fold_dir / arm
                folder.mkdir()
                targets[arm].to_frame().to_parquet(folder / "targets.parquet")
                for scenario in scenarios:
                    fr, result = evaluate(
                        folder / scenario, bars, targets[arm], seed, name, arm, scenario
                    )
                    results[arm][scenario][name] = fr
                    if arm == "v1_control":
                        for artifact in ("equity", "fills", "trades"):
                            pd.testing.assert_frame_equal(
                                getattr(result, artifact),
                                pd.read_parquet(source / scenario / f"{artifact}.parquet"),
                            )
                    if scenario == "base":
                        click.echo(
                            f"seed={seed} fold={name} {arm}: net={fr.net_return:.2%} DD={fr.max_drawdown:.2%} trades={fr.n_trades}"
                        )
            pd.DataFrame(rows).to_csv(output / "comparison.csv", index=False)
        for arm in ARMS:
            inputs[arm].append(
                SeedInput(
                    seed,
                    results[arm]["base"],
                    results[arm]["stress"],
                    {name: benchmarks[name, "buy_hold", "base"] for name in FOLDS},
                )
            )
            curves = {}
            for scenario in scenarios:
                curves[scenario] = _concatenate_equity(
                    [results[arm][scenario][name].equity_curve for name in FOLDS]
                )
                curves[scenario].to_frame("equity").to_parquet(
                    output / f"seed_{seed}" / f"{arm}_{scenario}_concatenated.parquet"
                )
            plot_curves(
                curves,
                output / f"seed_{seed}" / f"{arm}_concatenated.png",
                f"Iteration 12, seed {seed}, {arm}",
            )
    decisions = {}
    for arm in ARMS:
        verdict = evaluate_all(inputs[arm])
        save_verdict(verdict, output / f"{arm}_verdict.json")
        if arm == "v1_control" and verdict_to_dict(verdict) != json.loads(
            (SOURCE / "v1_matched_verdict.json").read_text()
        ):
            raise ValueError("Veredicto del control no reproducido")
        decisions[arm] = {"passes": verdict.passes, "seeds_passing": verdict.seeds_passing}
    report = {
        "decision": decisions,
        "models_trained": 0,
        "source_control_reproduced": True,
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
                "test_evaluated": False,
                "criterion_sha256": criterion_sha256(),
                "models_trained": 0,
            },
            tracking_uri,
            "spot-iteration-12-regime-gate",
        )
    click.echo(json.dumps(report))
    return report


@click.command()
@click.option("--output", type=click.Path(file_okay=False, path_type=Path))
@click.option("--tracking-uri", default="http://localhost:5000")
@click.option("--no-mlflow", is_flag=True)
def main(output, tracking_uri, no_mlflow):
    output = output or ROOT / "data/experiments" / (
        "iteration-12-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    run_iteration(output, None if no_mlflow else tracking_uri)


if __name__ == "__main__":
    main()
