"""Run a predeclared threshold diagnostic or an internal training walk-forward."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import click
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from xgboost import XGBClassifier

from src.backtesting.benchmarks import benchmark_targets
from src.backtesting.dataset import load_dataset
from src.backtesting.diagnostics import CONFIDENCES, classification_diagnostics, sensitivity
from src.backtesting.engine import ExecutionConfig, run_backtest
from src.backtesting.experiment import plot_results, track_results, write_json
from src.backtesting.metrics import compute_metrics
from src.models.xgboost.classifier import ModelConfig, fit_predict
from src.training.walk_forward import FOLD_BOUNDARIES, training_folds

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)


def verified_predictions(baseline: Path, data) -> tuple[pd.DataFrame, ExecutionConfig, ModelConfig]:
    recipe = json.loads((baseline / "recipe.json").read_text())
    if recipe["dataset_metadata"]["sha256"] != data.metadata["sha256"]:
        raise ValueError("El baseline procede de otro dataset")
    predictions = pd.read_parquet(baseline / "validation_predictions.parquet")
    if not predictions.index.equals(data.validation_features.index):
        raise ValueError("Las predicciones no corresponden a validation")
    model = XGBClassifier()
    model.load_model(baseline / "model.ubj")
    reproduced = model.predict_proba(data.validation_features)
    if not np.allclose(
        reproduced, predictions[["p_down", "p_neutral", "p_up"]], atol=1e-7, rtol=1e-7
    ):
        raise ValueError("Las predicciones difieren del modelo guardado")
    return predictions, ExecutionConfig(**recipe["execution"]), ModelConfig(**recipe["model"])


def evaluate_window(data, predictions, execution, model_config, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    classification = classification_diagnostics(
        predictions, data.validation_returns, model_config.threshold
    )
    table, results = sensitivity(data.validation_bars, predictions, execution)
    table.to_csv(output / "sensitivity.csv", index=False)
    write_json(output / "classification.json", classification)
    predictions.to_parquet(output / "predictions.parquet")
    benchmarks = {}
    for name, targets in benchmark_targets(data.validation_bars, data.benchmark_features).items():
        if name == "random":
            continue
        result = run_backtest(data.validation_bars, targets, execution)
        benchmarks[name] = compute_metrics(result)
        results[name] = result
    for name, result in results.items():
        directory = output / name
        directory.mkdir()
        for artifact in ("equity", "fills", "trades"):
            getattr(result, artifact).to_parquet(directory / f"{artifact}.parquet")
    plot_results(results, output)
    report = {
        "classification": classification,
        "sensitivity": json.loads(table.to_json(orient="records", double_precision=15)),
        "benchmarks": benchmarks,
        "train_rows": len(data.train_features),
        "evaluation_rows": len(predictions),
        "train_last_available_at": data.train_features.index.max().isoformat(),
        "evaluation_first_available_at": predictions.index.min().isoformat(),
        "evaluation_last_available_at": predictions.index.max().isoformat(),
    }
    write_json(output / "report.json", report)
    return report


@click.command()
@click.option(
    "--dataset", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option(
    "--baseline",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Run original con modelo y predicciones; requerido para diagnosticar 2024",
)
@click.option("--walk-forward", is_flag=True, help="Cuatro folds dentro de train; no evalúa 2024")
@click.option("--output", type=click.Path(file_okay=False, path_type=Path))
@click.option("--tracking-uri", default="http://localhost:5000", envvar="MLFLOW_TRACKING_URI")
@click.option("--no-mlflow", is_flag=True)
def main(dataset, baseline, walk_forward, output, tracking_uri, no_mlflow):
    if not walk_forward and baseline is None:
        raise click.UsageError("--baseline es obligatorio para el diagnóstico de validation")
    partition = "train_internal_walk_forward" if walk_forward else "validation_diagnostic"
    output = output or ROOT / "data" / "experiments" / (
        partition + "-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    try:
        data = load_dataset(dataset)
        execution, model_config = ExecutionConfig(), ModelConfig()
        baseline_predictions = None
        if not walk_forward:
            baseline_predictions, execution, model_config = verified_predictions(baseline, data)
        output.mkdir(parents=True, exist_ok=False)
        # Persist the protocol before evaluating any candidate. No best-threshold selection.
        write_json(
            output / "protocol.json",
            {
                "partition": partition,
                "confidences": CONFIDENCES,
                "fold_boundaries": FOLD_BOUNDARIES if walk_forward else None,
                "model": asdict(model_config),
                "execution": asdict(execution),
                "dataset_sha256": data.metadata["sha256"],
                "baseline": str(baseline.resolve()) if baseline and not walk_forward else None,
                "baseline_sha256": (
                    {
                        name: hashlib.sha256((baseline / name).read_bytes()).hexdigest()
                        for name in ("recipe.json", "model.ubj", "validation_predictions.parquet")
                    }
                    if baseline and not walk_forward
                    else None
                ),
                "source_sha256": {
                    str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest()
                    for directory in ("backtesting", "training", "models/xgboost")
                    for file in sorted((ROOT / "src" / directory).glob("*.py"))
                },
                "libraries": {
                    name: version(name)
                    for name in ("xgboost", "numpy", "pandas", "scikit-learn", "mlflow")
                },
                "test_evaluated": False,
                "selected_threshold": None,
                "notes": "Fixed sensitivity grid; UP must remain argmax. Gross/fees/net each compound their own cash. No hyperparameter search, no automatic promotion. Validation diagnostics are exploratory.",
            },
        )
        reports, metrics = {}, {}
        windows = training_folds(data) if walk_forward else [(data.metadata["train_end"][:4], data)]
        for name, window in windows:
            click.echo(
                f"{partition}: {name}; train={len(window.train_features)}, evaluación={len(window.validation_features)}"
            )
            folder = output / name
            if walk_forward:
                model, predictions, _ = fit_predict(window, model_config)
                folder.mkdir()
                model.save_model(folder / "model.ubj")
            else:
                predictions = baseline_predictions
            report = evaluate_window(window, predictions, execution, model_config, folder)
            reports[name] = report
            metrics[f"{name}.classification"] = {
                "balanced_accuracy": report["classification"]["balanced_accuracy"]
            }
            for row in report["sensitivity"]:
                metrics[f"{name}.p{int(round(row['confidence'] * 100))}.{row['scenario']}"] = {
                    key: value for key, value in row.items() if isinstance(value, int | float)
                }
                if row["scenario"] == "net":
                    duration = (
                        f"{row['mean_hold_minutes']:.1f} min"
                        if row["mean_hold_minutes"] is not None
                        else "n/a"
                    )
                    click.echo(
                        f"  p_up>={row['confidence']:.2f}: retorno={row['total_return']:.2%}, exposición={row['exposure']:.2%}, trades={row['trades']}, duración media={duration}"
                    )
            for strategy, values in report["benchmarks"].items():
                metrics[f"{name}.{strategy}"] = values
        write_json(
            output / "report.json",
            {
                "partition": partition,
                "windows": reports,
                "test_evaluated": False,
                "selected_threshold": None,
            },
        )
        if not no_mlflow:
            run_id = track_results(
                output,
                metrics,
                {
                    "partition": partition,
                    "test_evaluated": False,
                    "confidences": str(CONFIDENCES),
                    "selection": "none",
                    "dataset_features_sha256": data.metadata["sha256"]["features.parquet"],
                },
                tracking_uri,
                "spot-diagnostics-v1",
            )
            click.echo(f"MLflow run: {run_id}")
        click.echo(f"Informe: {output}. No se ha seleccionado ni promovido ningún umbral.")
    except Exception as exc:
        raise click.ClickException(
            f"Diagnóstico incompleto: {exc}; resultados locales: {output}"
        ) from exc


if __name__ == "__main__":
    main()
