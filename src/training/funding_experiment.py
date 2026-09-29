"""Iteration 11: preregistered settled funding versus paired v1 classification."""

import hashlib
import subprocess
from dataclasses import asdict, replace
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import click
import numpy as np
import pandas as pd
from dotenv import load_dotenv

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
from src.backtesting.policies import multiclass_policies, policy_metrics
from src.features.funding import (
    FUNDING_COLUMNS,
    align_funding,
    build_funding_features,
    load_audited_funding,
)
from src.models.xgboost.classifier import ModelConfig, fit_predict
from src.training.regime_experiment import paired_folds
from src.training.regression_experiment import fold_result, plot_curves, save_result
from src.training.walk_forward import training_folds

ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = "aa8f480"
ARMS = ("funding", "v1_matched")


def run_iteration(dataset, funding, output, tracking_uri):
    # Freeze source as well as recipe before observing any outcomes.
    dirty = subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            "src",
            "docs/iteration-11-protocol.md",
            "docs/risk-return-v1.yaml",
        ],
        cwd=ROOT,
        text=True,
    ).strip()
    if dirty:
        raise ValueError("Registrar código y protocolo en Git antes de entrenar")
    data = load_dataset(dataset, train_only=True)
    if (
        len(data.train_features.columns) != 20
        or data.metadata["train_end"] != "2024-01-01"
        or data.metadata["sha256"]["features.parquet"]
        != "97b7422532ada297de2f0e83665adeda3594a31b932a155b3028b7c00cd995a8"
    ):
        raise ValueError("La receta exige el snapshot v1 preregistrado hasta 2023")
    for filename, expected in {
        "observations.parquet": "ed8b4a2dcff5db65c3ecefaa98a5d1c1bd8381f04d0e91666c059712d409b47a",
        "manifest.csv": "f8c804975a854c46f9f2b412ba1ae4e6acf645a671931a8af1eb7d1c573c99e5",
    }.items():
        if hashlib.sha256((funding / filename).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Snapshot funding distinto al preregistro: {filename}")
    output.mkdir(parents=True, exist_ok=False)
    protocol_file = ROOT / "docs/iteration-11-protocol.md"
    criterion_file = ROOT / "docs/risk-return-v1.yaml"
    # Refuse to train if either preregistered document has changed since registration.
    for file in (protocol_file, criterion_file):
        registered = subprocess.check_output(
            ["git", "show", f"{PREREGISTRATION}:{file.relative_to(ROOT).as_posix()}"], cwd=ROOT
        )
        if registered.replace(b"\r\n", b"\n") != file.read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError(f"Documento distinto del preregistro: {file.name}")
        (output / file.name).write_bytes(file.read_bytes())
    execution = ExecutionConfig()
    scenarios = {
        "gross": replace(execution, maker_fee=0, taker_fee=0, slippage=0),
        "base": execution,
        "stress": replace(execution, slippage=0.0002),
    }
    manifest = {
        "preregistration_commit": PREREGISTRATION,
        "protocol_sha256": hashlib.sha256(protocol_file.read_bytes()).hexdigest(),
        "criterion_sha256": criterion_sha256(),
        "git_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "dataset": str(dataset.resolve()),
        "dataset_metadata": data.metadata,
        "features": {
            "v1_matched": list(data.train_features.columns),
            "funding": [*data.train_features.columns, *FUNDING_COLUMNS],
        },
        "seeds": SEEDS,
        "folds": FOLDS,
        "model": asdict(ModelConfig()),
        "funding_columns": FUNDING_COLUMNS,
        "availability_is_assumption": True,
        "policy": "UP argmax and p_up >= 0.50; hold_60m",
        "minimum_hold_minutes": 60,
        "execution": {k: asdict(v) for k, v in scenarios.items()},
        "validation_2024_evaluated": False,
        "test_evaluated": False,
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "src").rglob("*.py"))
        },
        "libraries": {
            name: version(name)
            for name in ("xgboost", "numpy", "pandas", "scikit-learn", "mlflow", "pyarrow")
        },
    }
    write_json(output / "protocol.json", manifest)
    events = load_audited_funding(funding)
    features = build_funding_features(data.train_features, events)
    features.to_parquet(output / "funding_features.parquet")
    align_funding(data.train_features.index, events).to_parquet(
        output / "funding_alignment.parquet"
    )
    write_json(
        output / "funding_metadata.json",
        {
            "snapshot_sha256": hashlib.sha256(
                (funding / "observations.parquet").read_bytes()
            ).hexdigest(),
            "manifest_sha256": hashlib.sha256((funding / "manifest.csv").read_bytes()).hexdigest(),
            "features_sha256": hashlib.sha256(
                (output / "funding_features.parquet").read_bytes()
            ).hexdigest(),
            "rows": len(features),
            "columns": list(features.columns),
            "first_available_at": features.index.min().isoformat(),
            "availability_is_assumption": True,
        },
    )
    folds = list(paired_folds(data, features))
    coverage = []
    for name, (_, original), (_, control, candidate) in zip(
        FOLDS, training_folds(data), folds, strict=True
    ):
        if not control.train_features.index.equals(candidate.train_features.index):
            raise ValueError("Train no emparejado")
        if not control.validation_features.index.equals(candidate.validation_features.index):
            raise ValueError("Predicciones no emparejadas")
        coverage.append(
            {
                "fold": name,
                "original_train_rows": len(original.train_features),
                "train_rows": len(control.train_features),
                "train_coverage": len(control.train_features) / len(original.train_features),
                "original_prediction_rows": len(original.validation_features),
                "prediction_rows": len(control.validation_features),
                "prediction_coverage": len(control.validation_features)
                / len(original.validation_features),
                "execution_bars": len(control.validation_bars),
            }
        )
    if any(row["train_coverage"] < 0.95 or row["prediction_coverage"] < 0.95 for row in coverage):
        raise ValueError("Cobertura funding inferior al 95%")
    pd.DataFrame(coverage).to_csv(output / "coverage.csv", index=False)
    rows, logged, benchmarks = [], {}, {}
    for name, (_, window, _candidate) in zip(FOLDS, folds, strict=True):
        for arm, position in (("buy_hold", 1), ("cash", 0)):
            result = run_backtest(
                window.validation_bars,
                pd.Series(position, index=window.validation_bars.index),
                execution,
            )
            metrics = policy_metrics(result)
            save_result(output / "benchmarks" / name / arm, result)
            benchmarks[name, arm] = fold_result(name, result, metrics)
            rows.append({"seed": None, "fold": name, "arm": arm, "scenario": "base", **metrics})
    inputs = {arm: [] for arm in ARMS}
    for seed in SEEDS:
        per_arm = {arm: {scenario: {} for scenario in scenarios} for arm in ARMS}
        for name, (_, window, candidate) in zip(FOLDS, folds, strict=True):
            click.echo(
                f"seed={seed} fold={name}: train={len(window.train_features)} eval={len(window.validation_features)}",
                err=False,
            )
            for arm in ARMS:
                folder = output / f"seed_{seed}" / name / arm
                folder.mkdir(parents=True)
                config = ModelConfig(seed=seed)
                arm_window = candidate if arm == "funding" else window
                model, predictions, diagnostics = fit_predict(arm_window, config)
                predictions["actual_return"] = arm_window.validation_returns
                targets = multiclass_policies(window.validation_bars.index, predictions)["hold_60m"]
                model.save_model(folder / "model.ubj")
                # Ensure the serialized artifact reproduces the exact predictions used.
                restored = type(model)()
                restored.load_model(folder / "model.ubj")
                original = predictions[["p_down", "p_neutral", "p_up"]].to_numpy()
                reproduced = restored.predict_proba(arm_window.validation_features)
                if not np.array_equal(original, reproduced):
                    raise ValueError("Predicciones distintas al recargar el modelo")
                predictions.to_parquet(folder / "predictions.parquet")
                targets.to_frame().to_parquet(folder / "targets.parquet")
                write_json(folder / "diagnostics.json", diagnostics)
                pd.Series(
                    model.feature_importances_,
                    index=arm_window.train_features.columns,
                    name="importance",
                ).to_csv(folder / "feature_importance.csv")
                logged[f"{seed}.{name}.{arm}.diagnostics"] = diagnostics.get(
                    "evaluation", diagnostics
                )
                curves = {}
                for scenario, costs in scenarios.items():
                    result = run_backtest(window.validation_bars, targets, costs)
                    metrics = policy_metrics(result)
                    save_result(folder / scenario, result)
                    per_arm[arm][scenario][name] = fold_result(name, result, metrics)
                    rows.append(
                        {"seed": seed, "fold": name, "arm": arm, "scenario": scenario, **metrics}
                    )
                    logged[f"{seed}.{name}.{arm}.{scenario}"] = metrics
                    curves[scenario] = result.equity.equity
                    if scenario == "base":
                        click.echo(
                            f"  {arm}: net={metrics['total_return']:.2%}, DD={metrics['max_drawdown']:.2%}, trades={metrics['trades']}"
                        )
                plot_curves(
                    curves, folder / "curves.png", f"Internal fold {name}, seed {seed}, {arm}"
                )
            # Persist partial progress after every paired fold.
            pd.DataFrame(rows).to_csv(output / "comparison.csv", index=False)
        for arm in ARMS:
            inputs[arm].append(
                SeedInput(
                    seed,
                    per_arm[arm]["base"],
                    per_arm[arm]["stress"],
                    {name: benchmarks[name, "buy_hold"] for name in FOLDS},
                )
            )
            curves = {}
            for scenario in scenarios:
                equity = _concatenate_equity(
                    [per_arm[arm][scenario][name].equity_curve for name in FOLDS]
                )
                curves[scenario] = equity
                equity.to_frame("equity").to_parquet(
                    output / f"seed_{seed}" / f"{arm}_{scenario}_concatenated.parquet"
                )
            plot_curves(
                curves,
                output / f"seed_{seed}" / f"{arm}_concatenated.png",
                f"Internal 2022-2023, seed {seed}, {arm}",
            )
    decisions = {}
    for arm in ARMS:
        verdict = evaluate_all(inputs[arm])
        save_verdict(verdict, output / f"{arm}_verdict.json")
        decisions[arm] = {"passes": verdict.passes, "seeds_passing": verdict.seeds_passing}
        logged[f"decision.{arm}"] = decisions[arm]
    report = {
        "decision": decisions,
        "validation_2024_evaluated": False,
        "test_evaluated": False,
        "promoted": False,
    }
    write_json(output / "report.json", report)
    if tracking_uri:
        run_id = track_results(
            output,
            logged,
            {
                "partition": "train_internal_walk_forward",
                "preregistration_commit": PREREGISTRATION,
                "criterion_sha256": criterion_sha256(),
                "test_evaluated": False,
            },
            tracking_uri,
            "spot-iteration-11-funding",
        )
        click.echo(f"MLflow run: {run_id}")
    click.echo(f"Decisión: {decisions}. Artifacts: {output}")
    return report


@click.command()
@click.option(
    "--dataset", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option(
    "--funding", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--output", type=click.Path(file_okay=False, path_type=Path))
@click.option("--tracking-uri", default="http://localhost:5000", envvar="MLFLOW_TRACKING_URI")
@click.option("--no-mlflow", is_flag=True)
def main(dataset, funding, output, tracking_uri, no_mlflow):
    load_dotenv(ROOT / ".env", override=False)
    output = output or ROOT / "data/experiments" / (
        "iteration-11-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    try:
        run_iteration(dataset, funding, output, None if no_mlflow else tracking_uri)
    except Exception as exc:
        raise click.ClickException(f"Iteración 11 incompleta: {exc}; artifacts: {output}") from exc


if __name__ == "__main__":
    main()
