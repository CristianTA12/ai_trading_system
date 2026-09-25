"""Predeclared exit-policy controls, followed by a binary one-hour target experiment."""

import hashlib
import json
from dataclasses import asdict, replace
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
from src.backtesting.engine import ExecutionConfig, run_backtest
from src.backtesting.experiment import plot_results, track_results, write_json
from src.backtesting.policies import (
    EXIT_POLICIES,
    multiclass_policies,
    policy_metrics,
    stateful_targets,
)
from src.models.xgboost.classifier import ModelConfig
from src.models.xgboost.hourly import HORIZON, fit_hourly, hourly_labels
from src.training.diagnose_xgboost import verified_predictions
from src.training.walk_forward import FOLD_BOUNDARIES, training_folds

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)


def hourly_folds(data, labels):
    """Future gaps exclude training targets/scoring, not live prediction availability."""
    for name, window in training_folds(data, HORIZON):
        train_index = window.train_features.index.intersection(labels.index)
        yield (
            name,
            replace(
                window,
                train_features=window.train_features.loc[train_index],
                train_returns=labels.loc[train_index, "target_return"],
                validation_returns=labels.target_return.reindex(window.validation_features.index),
            ),
        )


def cached_fold_predictions(folder: Path, window) -> pd.DataFrame:
    predictions = pd.read_parquet(folder / "predictions.parquet")
    if not predictions.index.equals(window.validation_features.index):
        raise ValueError("Predicciones guardadas no corresponden al fold")
    model = XGBClassifier()
    model.load_model(folder / "model.ubj")
    expected = model.predict_proba(window.validation_features)
    if not np.allclose(
        expected, predictions[["p_down", "p_neutral", "p_up"]], atol=1e-7, rtol=1e-7
    ):
        raise ValueError("No se reproducen las predicciones del modelo guardado")
    return predictions


def evaluate_policies(window, targets: dict, folder: Path, execution: ExecutionConfig) -> list:
    rows, plotted = [], {}
    for name, signals in targets.items():
        for scenario, config in (
            ("gross", replace(execution, maker_fee=0, taker_fee=0, slippage=0)),
            ("net", execution),
        ):
            result = run_backtest(window.validation_bars, signals, config)
            rows.append({"policy": name, "scenario": scenario, **policy_metrics(result)})
            artifact_dir = folder / name / scenario
            artifact_dir.mkdir(parents=True)
            for artifact in ("equity", "fills", "trades"):
                getattr(result, artifact).to_parquet(artifact_dir / f"{artifact}.parquet")
            if scenario == "net":
                plotted[name] = result
    for name, signals in benchmark_targets(
        window.validation_bars, window.benchmark_features
    ).items():
        if name == "random":
            continue
        result = run_backtest(window.validation_bars, signals, execution)
        rows.append({"policy": name, "scenario": "net", **policy_metrics(result)})
        plotted[name] = result
    cash = run_backtest(
        window.validation_bars, pd.Series(0, index=window.validation_bars.index), execution
    )
    rows.append({"policy": "cash", "scenario": "net", **policy_metrics(cash)})
    pd.DataFrame(rows).to_csv(folder / "comparison.csv", index=False)
    plot_results(plotted, folder)
    return rows


@click.command()
@click.option("--mode", type=click.Choice(["exits", "hourly"]), required=True)
@click.option(
    "--dataset", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--baseline", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--fold-baseline", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--output", type=click.Path(file_okay=False, path_type=Path))
@click.option("--tracking-uri", default="http://localhost:5000", envvar="MLFLOW_TRACKING_URI")
@click.option("--no-mlflow", is_flag=True)
def main(mode, dataset, baseline, fold_baseline, output, tracking_uri, no_mlflow):
    if mode == "exits" and (baseline is None or fold_baseline is None):
        raise click.UsageError("La política sin reentrenar requiere --baseline y --fold-baseline")
    output = output or ROOT / "data" / "experiments" / (
        mode + "-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    try:
        data = load_dataset(dataset)
        execution, model_config = ExecutionConfig(), ModelConfig(threshold=0.005)
        validation_predictions = None
        if mode == "exits":
            validation_predictions, execution, model_config = verified_predictions(baseline, data)
            prior = json.loads((fold_baseline / "protocol.json").read_text())
            if (
                prior["dataset_sha256"] != data.metadata["sha256"]
                or prior["execution"] != asdict(execution)
                or prior["model"] != asdict(model_config)
                or prior["fold_boundaries"] != list(FOLD_BOUNDARIES)
            ):
                raise ValueError("El baseline de folds no comparte dataset, parámetros y fronteras")
        output.mkdir(parents=True, exist_ok=False)
        protocol = {
            "mode": mode,
            "test_evaluated": False,
            "selected_policy": None,
            "model": asdict(model_config),
            "execution": asdict(execution),
            "model_fitted": mode == "hourly",
            "dataset_sha256": data.metadata["sha256"],
            "fold_boundaries": FOLD_BOUNDARIES,
            "policies": (
                EXIT_POLICIES if mode == "exits" else {"binary_immediate": 0, "binary_hold_60m": 60}
            ),
            "target": (
                "original 15m three-class"
                if mode == "exits"
                else "UP iff close(t+45m)/open(t)-1 > 0.005; label_end=t+60m; four consecutive bars"
            ),
            "entry_confidence": model_config.confidence,
            "missing_signal": "force flat at next observed open, overriding minimum hold",
            "minimum_hold": "elapsed time since entry; ignore early exits, do not latch; final liquidation overrides hold",
            "binary_exit": "NOT-UP after minimum hold; NOT-UP is not DOWN",
            "scope": (
                "internal train folds plus exploratory 2024"
                if mode == "exits"
                else "internal train folds only; no evaluation in 2024"
            ),
            "source_sha256": {
                str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest()
                for directory in ("backtesting", "training", "models/xgboost")
                for file in sorted((ROOT / "src" / directory).glob("*.py"))
            },
            "libraries": {
                name: version(name)
                for name in ("xgboost", "pandas", "numpy", "scikit-learn", "mlflow")
            },
        }
        if mode == "exits":
            sources = [
                baseline / name
                for name in ("recipe.json", "model.ubj", "validation_predictions.parquet")
            ]
            sources += [fold_baseline / "protocol.json"]
            sources += [
                fold_baseline / fold / name
                for fold in FOLD_BOUNDARIES[:-1]
                for name in ("model.ubj", "predictions.parquet")
            ]
            protocol["input_sha256"] = {
                str(file.resolve()): hashlib.sha256(file.read_bytes()).hexdigest()
                for file in sources
            }
        write_json(output / "protocol.json", protocol)
        if mode == "hourly":
            labels = hourly_labels(data.train_bars, data.train_features.index)
            labels.to_parquet(output / "hourly_train_labels.parquet")
        windows = (
            list(hourly_folds(data, labels)) if mode == "hourly" else list(training_folds(data))
        )
        if mode == "exits":
            windows.append(("2024_exploratory", data))
        reports, metrics, all_rows = {}, {}, []
        for name, window in windows:
            folder = output / name
            folder.mkdir()
            click.echo(
                f"{mode}: {name}; train={len(window.train_features)}, evaluación={len(window.validation_features)}"
            )
            classification = None
            if mode == "hourly":
                model, predictions, classification = fit_hourly(window, model_config)
                model.save_model(folder / "model.ubj")
                write_json(folder / "classification.json", classification)
                entries = predictions.p_up >= model_config.confidence
                targets = {
                    policy: stateful_targets(
                        window.validation_bars.index, entries, ~entries, minutes
                    )
                    for policy, minutes in (("binary_immediate", 0), ("binary_hold_60m", 60))
                }
            else:
                predictions = (
                    validation_predictions
                    if name == "2024_exploratory"
                    else cached_fold_predictions(fold_baseline / name, window)
                )
                targets = multiclass_policies(
                    window.validation_bars.index, predictions, model_config.confidence
                )
            predictions.to_parquet(folder / "predictions.parquet")
            pd.DataFrame(targets).to_parquet(folder / "targets.parquet")
            rows = evaluate_policies(window, targets, folder, execution)
            report = {
                "train_rows": len(window.train_features),
                "evaluation_rows": len(predictions),
                "train_last_available_at": window.train_features.index.max().isoformat(),
                "evaluation_first_available_at": predictions.index.min().isoformat(),
                "evaluation_last_available_at": predictions.index.max().isoformat(),
                "classification": classification,
                "results": rows,
            }
            reports[name] = report
            write_json(folder / "report.json", report)
            for row in rows:
                all_rows.append({"window": name, **row})
                metrics[f"{name}.{row['policy']}.{row['scenario']}"] = {
                    k: v for k, v in row.items() if isinstance(v, int | float)
                }
                if row["scenario"] == "net" and row["policy"] in targets:
                    edge = (
                        f"{row['mean_trade_bps']:.2f}"
                        if row["mean_trade_bps"] is not None
                        else "n/a"
                    )
                    click.echo(
                        f"  {row['policy']}: retorno={row['total_return']:.2%}, trades={row['trades']}, exposición={row['exposure']:.2%}, media neta={edge} pb"
                    )
            if classification:
                metrics[f"{name}.classification"] = {
                    k: v for k, v in classification.items() if isinstance(v, int | float)
                }
        pd.DataFrame(all_rows).to_csv(output / "comparison.csv", index=False)
        write_json(
            output / "report.json",
            {"mode": mode, "windows": reports, "test_evaluated": False, "selected_policy": None},
        )
        if not no_mlflow:
            run_id = track_results(
                output,
                metrics,
                {
                    "partition": protocol["scope"],
                    "mode": mode,
                    "model_fitted": mode == "hourly",
                    "selection": "none",
                    "dataset_features_sha256": data.metadata["sha256"]["features.parquet"],
                },
                tracking_uri,
                "spot-exit-horizon-v1",
            )
            click.echo(f"MLflow run: {run_id}")
        click.echo(f"Informe: {output}. Test reservado; ninguna política promovida.")
    except Exception as exc:
        raise click.ClickException(f"Experimento incompleto: {exc}; resultados: {output}") from exc


if __name__ == "__main__":
    main()
