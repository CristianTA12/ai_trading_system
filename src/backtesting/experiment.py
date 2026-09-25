"""Reproducible validation experiments with local artifacts and remote MLflow tracking."""

import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from src.backtesting.benchmarks import benchmark_targets
from src.backtesting.dataset import load_dataset
from src.backtesting.engine import ExecutionConfig, run_backtest
from src.backtesting.metrics import compute_metrics
from src.models.xgboost.classifier import ModelConfig, fit_predict


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def track_results(output: Path, metrics: dict, params: dict, uri: str, experiment: str) -> str:
    # Low-level APIs work with both the MLflow 2.x server and 3.x clients.
    from mlflow.tracking import MlflowClient

    client = MlflowClient(tracking_uri=uri)
    existing = client.get_experiment_by_name(experiment)
    experiment_id = existing.experiment_id if existing else client.create_experiment(experiment)
    experiment_info = client.get_experiment(experiment_id)
    if not experiment_info.artifact_location.startswith("mlflow-artifacts:"):
        raise ValueError(
            "MLflow requiere un experimento nuevo con proxy de artifacts; consulta docs/backtesting.md"
        )
    run = client.create_run(
        experiment_id,
        tags={
            "mlflow.runName": output.name,
            "partition": str(params.get("partition", "validation")),
        },
    )
    run_id = run.info.run_id
    try:
        for key, value in params.items():
            client.log_param(run_id, key, value)
        for strategy, values in metrics.items():
            for key, value in values.items():
                if isinstance(value, int | float):
                    client.log_metric(run_id, f"{strategy}.{key}", value)
        write_json(
            output / "mlflow.json",
            {"run_id": run_id, "experiment_id": experiment_id, "tracking_uri": uri},
        )
        client.log_artifacts(run_id, str(output))
        client.set_terminated(run_id, "FINISHED")
    except Exception:
        client.set_terminated(run_id, "FAILED")
        raise
    return run_id


def plot_results(results: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for name, result in results.items():
        equity = result.equity.equity
        axes[0].plot(equity.index, equity / equity.iloc[0], label=name, linewidth=1)
        axes[1].plot(equity.index, 100 * (equity / equity.cummax() - 1), linewidth=1)
    axes[0].set(title="BTC/USDT spot — validation, net of costs", ylabel="Equity / initial capital")
    axes[0].legend()
    axes[1].set(ylabel="Drawdown (%)", xlabel="UTC")
    for axis in axes:
        axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(output / "comparison.png", dpi=160)
    plt.close(figure)


def run_experiment(
    dataset: Path,
    output: Path,
    execution: ExecutionConfig,
    model_config: ModelConfig | None,
    random_seeds: int = 30,
    tracking_uri: str | None = "http://localhost:5000",
    experiment_name: str = "spot-baseline-v1",
) -> dict:
    if random_seeds < 2:
        raise ValueError("Se requieren al menos dos semillas aleatorias")
    data = load_dataset(dataset)
    output.mkdir(parents=True, exist_ok=False)
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2], text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=Path(__file__).resolve().parents[2],
                text=True,
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = "unknown", True
    recipe = {
        "created_at": datetime.now(UTC).isoformat(),
        "dataset": str(dataset.resolve()),
        "dataset_metadata": data.metadata,
        "execution": asdict(execution),
        "model": asdict(model_config) if model_config else None,
        "git_revision": revision,
        "tracked_files_dirty": dirty,
        "source_sha256": {
            str(file.relative_to(Path(__file__).resolve().parents[2])): hashlib.sha256(
                file.read_bytes()
            ).hexdigest()
            for directory in ("backtesting", "models/xgboost", "training")
            for file in sorted((Path(__file__).resolve().parents[1] / directory).glob("*.py"))
        },
        "libraries": {
            name: version(name) for name in ("xgboost", "numpy", "pandas", "scikit-learn", "mlflow")
        },
        "partition": "validation",
        "test_evaluated": False,
        "train_rows": len(data.train_features),
        "validation_prediction_rows": len(data.validation_features),
        "validation_bars": len(data.validation_bars),
        "validation_gap_events": int(
            data.validation_bars.index.to_series()
            .diff()
            .dropna()
            .ne(pd.Timedelta(minutes=15))
            .sum()
        ),
        "random_seeds": list(range(42, 42 + random_seeds)),
        "metrics_convention": "daily UTC; 365 days; risk-free=0; drawdown at bar closes; undefined=null",
        "execution_assumption": "spot long/flat; available signal fills at same timestamp open; no latency; taker by default; maker fee scenario does not simulate limit fills",
        "missing_signal": "flat at next observed open; no fabricated gap fills",
    }
    write_json(output / "recipe.json", recipe)
    targets = benchmark_targets(data.validation_bars, data.benchmark_features)
    classification = None
    if model_config:
        model, predictions, classification = fit_predict(data, model_config)
        model.save_model(output / "model.ubj")
        predictions.to_parquet(output / "validation_predictions.parquet")
        write_json(output / "classification.json", classification)
        pd.Series(
            model.feature_importances_, index=data.train_features.columns, name="importance"
        ).sort_values(ascending=False).to_csv(output / "feature_importance.csv")
        targets["xgboost"] = predictions.target_position
    results, metrics = {}, {}
    for name, signals in targets.items():
        result = run_backtest(data.validation_bars, signals, execution)
        results[name], metrics[name] = result, compute_metrics(result)
        folder = output / name
        folder.mkdir()
        for artifact in ("equity", "fills", "trades"):
            getattr(result, artifact).to_parquet(folder / f"{artifact}.parquet")
    random_metrics = [{"seed": 42, **metrics["random"]}]
    for seed in range(43, 42 + random_seeds):
        signals = benchmark_targets(data.validation_bars, data.benchmark_features, seed)["random"]
        random_metrics.append(
            {
                "seed": seed,
                **compute_metrics(run_backtest(data.validation_bars, signals, execution)),
            }
        )
    distribution = pd.DataFrame(random_metrics).set_index("seed")
    distribution.to_csv(output / "random_distribution.csv")
    # Convert NaN (undefined ratios) to JSON null, never Infinity/NaN literals.
    quantiles = json.loads(distribution.quantile([0.05, 0.5, 0.95]).to_json(orient="index"))
    report = {
        "strategies": metrics,
        "random_quantiles": quantiles,
        "classification": classification,
        "test_evaluated": False,
        "output": str(output),
    }
    write_json(output / "report.json", report)
    pd.DataFrame(metrics).T.to_csv(output / "comparison.csv")
    plot_results(results, output)
    if tracking_uri:
        logged_metrics = {**metrics}
        if classification:
            logged_metrics["classification"] = classification
        params = {
            "partition": "validation",
            "dataset_features_sha256": data.metadata["sha256"]["features.parquet"],
            "train_rows": len(data.train_features),
            "validation_rows": len(data.validation_features),
            **asdict(execution),
            **({f"model_{k}": v for k, v in asdict(model_config).items()} if model_config else {}),
        }
        report["mlflow_run_id"] = track_results(
            output, logged_metrics, params, tracking_uri, experiment_name
        )
    return report
