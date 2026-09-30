"""Iteration 13: fixed four-hour recipe, regime ablation and matched 15m control."""

import hashlib
import subprocess
from dataclasses import asdict, replace
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import click
import numpy as np
import pandas as pd

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
from src.backtesting.policies import policy_metrics, stateful_targets
from src.backtesting.regime_gate import daily_regime, gated_targets
from src.models.xgboost.classifier import ModelConfig, fit_predict, position_targets
from src.models.xgboost.four_hour import HORIZON, THRESHOLD, four_hour_labels, paired_horizon_folds
from src.training.regression_experiment import fold_result, plot_curves, save_result
from src.training.walk_forward import training_folds

ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = "adb8758"
DATASET = ROOT / "data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z"
ARMS = ("four_hour_regime", "four_hour_control", "fifteen_min_regime")


def run_iteration(output: Path, tracking_uri: str | None):
    documents = ["docs/iteration-13-protocol.md", "docs/risk-return-v1.yaml"]
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--", "src", *documents], cwd=ROOT
    ).strip():
        raise ValueError("Registrar código y protocolo antes de entrenar")
    for name in documents:
        registered = subprocess.check_output(["git", "show", f"{PREREGISTRATION}:{name}"], cwd=ROOT)
        if registered.replace(b"\r\n", b"\n") != (ROOT / name).read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError(f"Documento distinto del preregistro: {name}")
    if (
        hashlib.sha256((DATASET / "metadata.json").read_bytes()).hexdigest()
        != "a6a80da91f7956a49b5641038ae047b5422fba800a60fa1c7df23c7fd2b42c35"
    ):
        raise ValueError("Snapshot distinto del preregistro")
    data = load_dataset(DATASET, train_only=True)
    labels = four_hour_labels(data.train_bars, data.train_features.index)
    gate = daily_regime(data.train_bars, data.train_bars.index)
    folds = list(paired_horizon_folds(data, labels))
    coverage = []
    for name, (_, original), (_, short, long) in zip(
        FOLDS, training_folds(data), folds, strict=True
    ):
        if not short.train_features.equals(
            long.train_features
        ) or not short.validation_features.equals(long.validation_features):
            raise ValueError("Features no emparejadas")
        coverage.append(
            {
                "fold": name,
                "original_train_rows": len(original.train_features),
                "train_rows": len(long.train_features),
                "train_coverage": len(long.train_features) / len(original.train_features),
                "prediction_rows": len(long.validation_features),
                "prediction_coverage": len(long.validation_features)
                / len(original.validation_features),
                "scored_4h_rows": int(long.validation_returns.notna().sum()),
                "bars": len(long.validation_bars),
                "regime_coverage": float(gate.loc[long.validation_bars.index, "valid"].mean()),
            }
        )
    if any(
        min(row["train_coverage"], row["prediction_coverage"], row["regime_coverage"]) < 0.95
        for row in coverage
    ):
        raise ValueError("Cobertura inferior al 95%")
    output.mkdir(parents=True, exist_ok=False)
    for name in documents:
        (output / Path(name).name).write_bytes((ROOT / name).read_bytes())
    labels.to_parquet(output / "four_hour_labels.parquet")
    gate.to_parquet(output / "regime.parquet")
    pd.DataFrame(coverage).to_csv(output / "coverage.csv", index=False)
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
            "dataset_metadata": data.metadata,
            "seeds": SEEDS,
            "folds": FOLDS,
            "arms": ARMS,
            "candidate": "four_hour_regime",
            "model_four_hour": asdict(ModelConfig(threshold=THRESHOLD)),
            "model_fifteen_min": asdict(ModelConfig()),
            "execution": {k: asdict(v) for k, v in scenarios.items()},
            "target": "close(t+3h45m)/open(t)-1; label_end=t+4h; 16 consecutive bars",
            "validation_2024_evaluated": False,
            "test_evaluated": False,
            "source_sha256": {
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT / "src").rglob("*.py"))
            },
            "artifact_sha256": {
                p: hashlib.sha256((output / p).read_bytes()).hexdigest()
                for p in ("four_hour_labels.parquet", "regime.parquet")
            },
            "libraries": {
                n: version(n)
                for n in ("xgboost", "numpy", "pandas", "scikit-learn", "mlflow", "pyarrow")
            },
        },
    )
    rows, logged, benchmarks = [], {}, {}

    def evaluate(folder, bars, targets, seed, fold, arm, scenario):
        result = run_backtest(bars, targets, scenarios[scenario])
        metrics = policy_metrics(result)
        save_result(folder, result)
        rows.append({"seed": seed, "fold": fold, "arm": arm, "scenario": scenario, **metrics})
        logged[f"{seed}.{fold}.{arm}.{scenario}"] = {
            k: metrics[k] for k in ("total_return", "sharpe", "max_drawdown", "trades", "exposure")
        }
        return fold_result(fold, result, metrics)

    for name, (_, short, long) in zip(FOLDS, folds, strict=True):
        bars = long.validation_bars
        folder = output / "folds" / name
        folder.mkdir(parents=True)
        pd.DataFrame(
            {
                "return_15m": short.train_returns,
                "return_4h": long.train_returns,
                "label_end_4h": long.train_features.index + HORIZON,
            }
        ).to_parquet(folder / "train_rows.parquet")
        for arm, targets in (
            ("buy_hold", pd.Series(1, index=bars.index)),
            ("cash", pd.Series(0, index=bars.index)),
            ("regime_only", gate.loc[bars.index, "allow_long"].astype(int)),
        ):
            for scenario in scenarios if arm == "regime_only" else ("base",):
                benchmarks[name, arm, scenario] = evaluate(
                    output / "benchmarks" / name / arm / scenario,
                    bars,
                    targets,
                    None,
                    name,
                    arm,
                    scenario,
                )
    inputs = {arm: [] for arm in ARMS}
    for seed in SEEDS:
        results = {arm: {scenario: {} for scenario in scenarios} for arm in ARMS}
        for name, (_, short, long) in zip(FOLDS, folds, strict=True):
            click.echo(
                f"seed={seed} fold={name}: train={len(long.train_features)} predictions={len(long.validation_features)}"
            )
            fold_dir = output / f"seed_{seed}" / name
            predictions = {}
            for model_name, window, threshold in (
                ("four_hour", long, THRESHOLD),
                ("fifteen_min", short, 0.0025),
            ):
                folder = fold_dir / model_name
                folder.mkdir(parents=True)
                model, pred, diagnostics = fit_predict(
                    window, ModelConfig(seed=seed, threshold=threshold)
                )
                model.save_model(folder / "model.ubj")
                restored = type(model)()
                restored.load_model(folder / "model.ubj")
                np.testing.assert_array_equal(
                    restored.predict_proba(window.validation_features),
                    pred[["p_down", "p_neutral", "p_up"]].to_numpy(),
                )
                pred["actual_return"] = window.validation_returns
                pred["label_end"] = pred.index + (
                    HORIZON if model_name == "four_hour" else pd.Timedelta(minutes=15)
                )
                pred.to_parquet(folder / "predictions.parquet")
                write_json(folder / "classification.json", diagnostics)
                pd.Series(
                    model.feature_importances_,
                    index=window.train_features.columns,
                    name="importance",
                ).to_csv(folder / "feature_importance.csv")
                predictions[model_name] = pred
            bars = long.validation_bars
            entries = position_targets(predictions["four_hour"], 0.5).astype(bool)
            targets = {
                "four_hour_regime": gated_targets(
                    bars.index, predictions["four_hour"], gate.allow_long, 240
                ),
                "four_hour_control": stateful_targets(bars.index, entries, ~entries, 240),
                "fifteen_min_regime": gated_targets(
                    bars.index, predictions["fifteen_min"], gate.allow_long, 60
                ),
            }
            for arm in ARMS:
                folder = fold_dir / arm
                folder.mkdir()
                targets[arm].to_frame().to_parquet(folder / "targets.parquet")
                for scenario in scenarios:
                    fr = evaluate(folder / scenario, bars, targets[arm], seed, name, arm, scenario)
                    results[arm][scenario][name] = fr
                    if scenario == "base":
                        click.echo(
                            f"  {arm}: net={fr.net_return:.2%} DD={fr.max_drawdown:.2%} trades={fr.n_trades}"
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
                f"Iteration 13, seed {seed}, {arm}",
            )
    decisions = {}
    for arm in ARMS:
        verdict = evaluate_all(inputs[arm])
        save_verdict(verdict, output / f"{arm}_verdict.json")
        decisions[arm] = {"passes": verdict.passes, "seeds_passing": verdict.seeds_passing}
    report = {
        "decision": decisions,
        "candidate": "four_hour_regime",
        "models_trained": 40,
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
                "criterion_sha256": criterion_sha256(),
                "test_evaluated": False,
            },
            tracking_uri,
            "spot-iteration-13-four-hour",
        )
    click.echo(str(report))
    return report


@click.command()
@click.option("--output", type=click.Path(file_okay=False, path_type=Path))
@click.option("--tracking-uri", default="http://localhost:5000")
@click.option("--no-mlflow", is_flag=True)
def main(output, tracking_uri, no_mlflow):
    output = output or ROOT / "data/experiments" / (
        "iteration-13-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    run_iteration(output, None if no_mlflow else tracking_uri)


if __name__ == "__main__":
    main()
