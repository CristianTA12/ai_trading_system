"""Paired v1/v2 walk-forward on identical rows, with a fixed one-hour hold policy."""

import hashlib
from dataclasses import asdict, replace
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import click
import pandas as pd
from dotenv import load_dotenv

from src.backtesting.dataset import load_dataset
from src.backtesting.engine import ExecutionConfig, run_backtest
from src.backtesting.experiment import plot_results, track_results, write_json
from src.backtesting.policies import multiclass_policies, policy_metrics
from src.features.regime import NEW_COLUMNS, PEAK_WINDOW, TREND_WINDOW, build_regime_features
from src.models.xgboost.classifier import ModelConfig, fit_predict
from src.training.walk_forward import FOLD_BOUNDARIES, training_folds

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)


def acceptance(rows: list[dict]) -> dict:
    """Report the preregistered gate, without choosing alternative features/policies."""
    counts = {}
    for arm in ("v1_matched", "v2"):
        net = [row for row in rows if row["arm"] == arm and row["scenario"] == "net"]
        if len(net) != 4 or len({row["fold"] for row in net}) != 4:
            raise ValueError("Se requieren los cuatro resultados netos de cada brazo")
        counts[arm] = sum(row["total_return"] > 0 for row in net)
    return {
        "positive_folds": counts,
        "required_positive_folds": 3,
        "v2_passes_preregistered_gate": counts["v2"] >= 3,
        "promoted": False,
        "test_evaluated": False,
    }


def paired_folds(data, features):
    """Align both training and prediction coverage, not merely evaluation labels."""
    common = data.train_features.index.intersection(features.index)
    matched = replace(
        data,
        train_features=data.train_features.loc[common],
        train_returns=data.train_returns.loc[common],
    )
    for name, control in training_folds(matched):
        candidate = replace(
            control,
            train_features=features.loc[control.train_features.index],
            validation_features=features.loc[control.validation_features.index],
        )
        yield name, control, candidate


@click.command()
@click.option(
    "--dataset", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--output", type=click.Path(file_okay=False, path_type=Path))
@click.option("--tracking-uri", default="http://localhost:5000", envvar="MLFLOW_TRACKING_URI")
@click.option("--no-mlflow", is_flag=True)
def main(dataset, output, tracking_uri, no_mlflow):
    output = output or ROOT / "data" / "experiments" / (
        "regime-v2-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    try:
        data = load_dataset(dataset)
        execution, model_config = ExecutionConfig(), ModelConfig()
        output.mkdir(parents=True, exist_ok=False)
        protocol_file = ROOT / "docs" / "features-v2-protocol.md"
        protocol = {
            "preregistration_commit": "a99a2ec",
            "preregistration_sha256": hashlib.sha256(protocol_file.read_bytes()).hexdigest(),
            "dataset_sha256": data.metadata["sha256"],
            "feature_version": 2,
            "new_columns": NEW_COLUMNS,
            "peak_window": PEAK_WINDOW,
            "trend_window": TREND_WINDOW,
            "model": asdict(model_config),
            "execution": asdict(execution),
            "policy": "hold_60m; original three-class 15m target; UP argmax and p_up >= 0.5",
            "coverage": "v1 and v2 trained/predicted on identical complete-case rows; missing signals force flat",
            "fold_boundaries": FOLD_BOUNDARIES,
            "required_positive_folds": 3,
            "historical_full_coverage_v1_hold_60m": {
                "positive_folds": 2,
                "returns_rounded": [-0.3309, -0.3636, 0.0968, 0.1204],
                "source_run": "b36f2b0eed65495aa7667b71dcd494b6",
            },
            "validation_2024_evaluated": False,
            "test_evaluated": False,
            "source_sha256": {
                str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest()
                for directory in ("features", "backtesting", "training", "models/xgboost")
                for file in sorted((ROOT / "src" / directory).glob("*.py"))
            },
            "libraries": {
                name: version(name)
                for name in ("xgboost", "numpy", "pandas", "scikit-learn", "mlflow")
            },
        }
        write_json(output / "protocol.json", protocol)
        (output / "preregistration.md").write_bytes(protocol_file.read_bytes())
        features = build_regime_features(data.train_bars, data.train_features)
        if features.empty:
            raise ValueError("No hay features después del warmup de 30 días")
        features.to_parquet(output / "features_v2_train.parquet")
        write_json(
            output / "features_metadata.json",
            {
                "columns": list(features.columns),
                "rows": len(features),
                "first_available_at": features.index.min().isoformat(),
                "last_available_at": features.index.max().isoformat(),
                "sha256": hashlib.sha256(
                    (output / "features_v2_train.parquet").read_bytes()
                ).hexdigest(),
            },
        )
        original_folds = dict(training_folds(data))
        coverage, reports, rows, logged = [], {}, [], {}
        for name, control, candidate in paired_folds(data, features):
            folder = output / name
            folder.mkdir()
            original = original_folds[name]
            fold_coverage = {
                "fold": name,
                "original_train_rows": len(original.train_features),
                "matched_train_rows": len(control.train_features),
                "original_prediction_rows": len(original.validation_features),
                "matched_prediction_rows": len(control.validation_features),
                "execution_bars": len(control.validation_bars),
                "train_last_available_at": control.train_features.index.max().isoformat(),
                "prediction_first_available_at": control.validation_features.index.min().isoformat(),
                "prediction_last_available_at": control.validation_features.index.max().isoformat(),
            }
            coverage.append(fold_coverage)
            click.echo(
                f"{name}: train={len(control.train_features)}, predicciones={len(control.validation_features)}/{len(original.validation_features)}"
            )
            plots, classification = {}, {}
            for arm, window in (("v1_matched", control), ("v2", candidate)):
                arm_dir = folder / arm
                arm_dir.mkdir()
                model, predictions, class_report = fit_predict(window, model_config)
                model.save_model(arm_dir / "model.ubj")
                predictions.to_parquet(arm_dir / "predictions.parquet")
                write_json(arm_dir / "classification.json", class_report)
                classification[arm] = class_report
                pd.Series(
                    model.feature_importances_,
                    index=window.train_features.columns,
                    name="importance",
                ).sort_values(ascending=False).to_csv(arm_dir / "feature_importance.csv")
                targets = multiclass_policies(
                    window.validation_bars.index, predictions, model_config.confidence
                )["hold_60m"]
                targets.to_frame().to_parquet(arm_dir / "targets.parquet")
                for scenario, config in (
                    ("gross", replace(execution, maker_fee=0, taker_fee=0, slippage=0)),
                    ("net", execution),
                ):
                    result = run_backtest(window.validation_bars, targets, config)
                    metrics = policy_metrics(result)
                    rows.append({"fold": name, "arm": arm, "scenario": scenario, **metrics})
                    logged[f"{name}.{arm}.{scenario}"] = metrics
                    result_dir = arm_dir / scenario
                    result_dir.mkdir()
                    for artifact in ("equity", "fills", "trades"):
                        getattr(result, artifact).to_parquet(result_dir / f"{artifact}.parquet")
                    if scenario == "net":
                        plots[arm] = result
                        edge = (
                            f"{metrics['mean_trade_bps']:.2f}"
                            if metrics["mean_trade_bps"] is not None
                            else "n/a"
                        )
                        click.echo(
                            f"  {arm}: retorno={metrics['total_return']:.2%}, trades={metrics['trades']}, exposición={metrics['exposure']:.2%}, media neta={edge} pb"
                        )
                logged[f"{name}.{arm}.classification"] = class_report
            for arm, target in (("buy_hold", 1), ("cash", 0)):
                result = run_backtest(
                    control.validation_bars,
                    pd.Series(target, index=control.validation_bars.index),
                    execution,
                )
                metrics = policy_metrics(result)
                rows.append({"fold": name, "arm": arm, "scenario": "net", **metrics})
                logged[f"{name}.{arm}.net"] = metrics
                plots[arm] = result
            plot_results(plots, folder)
            reports[name] = {
                "coverage": fold_coverage,
                "classification": classification,
                "results": [row for row in rows if row["fold"] == name],
            }
            write_json(folder / "report.json", reports[name])
        decision = acceptance(rows)
        pd.DataFrame(rows).to_csv(output / "comparison.csv", index=False)
        pd.DataFrame(coverage).to_csv(output / "coverage.csv", index=False)
        write_json(output / "report.json", {"decision": decision, "folds": reports})
        if not no_mlflow:
            logged["decision"] = {
                "v2_positive_folds": decision["positive_folds"]["v2"],
                "v1_matched_positive_folds": decision["positive_folds"]["v1_matched"],
                "required_positive_folds": 3,
            }
            run_id = track_results(
                output,
                logged,
                {
                    "partition": "train_internal_walk_forward",
                    "feature_version": 2,
                    "policy": "hold_60m",
                    "preregistration_commit": "a99a2ec",
                    "test_evaluated": False,
                    "dataset_features_sha256": data.metadata["sha256"]["features.parquet"],
                },
                tracking_uri,
                "spot-regime-v2",
            )
            click.echo(f"MLflow run: {run_id}")
        click.echo(f"Decisión: {decision}. Informe: {output}")
    except Exception as exc:
        raise click.ClickException(
            f"Experimento v2 incompleto: {exc}; resultados: {output}"
        ) from exc


if __name__ == "__main__":
    main()
