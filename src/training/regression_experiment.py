"""Iteration 10: five seeds, four internal folds, paired regression/classification."""

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
    FoldResult,
    SeedInput,
    _concatenate_equity,
    criterion_sha256,
    evaluate_all,
    save_verdict,
)
from src.backtesting.experiment import track_results, write_json
from src.backtesting.policies import multiclass_policies, policy_metrics
from src.models.xgboost.classifier import ModelConfig, fit_predict
from src.models.xgboost.regressor import fit_predict_regression, regression_targets
from src.training.walk_forward import training_folds

ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = "d3cfde6"
ARMS = ("regression", "classifier")


def fold_result(name, result, metrics):
    """Cash is established from the execution ledger, not inferred from returns."""
    equity = result.equity.equity
    is_cash = bool(
        result.fills.empty
        and result.trades.empty
        and (result.equity.quantity == 0).all()
        and (equity == equity.iloc[0]).all()
    )
    return FoldResult(
        name,
        metrics["total_return"],
        metrics["max_drawdown"],
        metrics["sharpe"],
        equity,
        len(result.trades),
        len(result.fills),
        is_cash,
    )


def save_result(folder, result):
    folder.mkdir(parents=True)
    for artifact in ("equity", "fills", "trades"):
        getattr(result, artifact).to_parquet(folder / f"{artifact}.parquet")


def plot_curves(curves, path, title):
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for name, equity in curves.items():
        axes[0].plot(equity.index, equity / equity.iloc[0], label=name, linewidth=1)
        axes[1].plot(equity.index, 100 * (equity / equity.cummax() - 1), linewidth=1)
    axes[0].set(title=title, ylabel="Equity / initial")
    axes[0].legend()
    axes[1].set(ylabel="Drawdown (%)", xlabel="UTC")
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def run_iteration(dataset, output, tracking_uri):
    data = load_dataset(dataset, train_only=True)
    if len(data.train_features.columns) != 20:
        raise ValueError("La receta exige las 20 features v1")
    output.mkdir(parents=True, exist_ok=False)
    protocol_file = ROOT / "docs/iteration-10-protocol.md"
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
        "features": list(data.train_features.columns),
        "seeds": SEEDS,
        "folds": FOLDS,
        "model": asdict(ModelConfig()),
        "regression_objective": "reg:squarederror",
        "entry_threshold": 0.0015,
        "exit_below": 0,
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
    folds = list(training_folds(data))
    coverage = []
    for name, (_, window) in zip(FOLDS, folds, strict=True):
        coverage.append(
            {
                "fold": name,
                "train_rows": len(window.train_features),
                "prediction_rows": len(window.validation_features),
                "execution_bars": len(window.validation_bars),
                "train_last": window.train_features.index.max().isoformat(),
                "eval_first": window.validation_features.index.min().isoformat(),
                "eval_last": window.validation_features.index.max().isoformat(),
            }
        )
    pd.DataFrame(coverage).to_csv(output / "coverage.csv", index=False)
    rows, logged, benchmarks = [], {}, {}
    for name, (_, window) in zip(FOLDS, folds, strict=True):
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
        for name, (_, window) in zip(FOLDS, folds, strict=True):
            click.echo(
                f"seed={seed} fold={name}: train={len(window.train_features)} eval={len(window.validation_features)}",
                err=False,
            )
            for arm in ARMS:
                folder = output / f"seed_{seed}" / name / arm
                folder.mkdir(parents=True)
                config = ModelConfig(seed=seed)
                if arm == "regression":
                    model, predictions, diagnostics = fit_predict_regression(window, config)
                    targets = regression_targets(
                        window.validation_bars.index, predictions.predicted_return
                    )
                else:
                    model, predictions, diagnostics = fit_predict(window, config)
                    predictions["actual_return"] = window.validation_returns
                    targets = multiclass_policies(window.validation_bars.index, predictions)[
                        "hold_60m"
                    ]
                model.save_model(folder / "model.ubj")
                # Ensure the serialized artifact reproduces the exact predictions used.
                restored = type(model)()
                restored.load_model(folder / "model.ubj")
                original = (
                    predictions.predicted_return.to_numpy()
                    if arm == "regression"
                    else predictions[["p_down", "p_neutral", "p_up"]].to_numpy()
                )
                reproduced = (
                    restored.predict(window.validation_features)
                    if arm == "regression"
                    else restored.predict_proba(window.validation_features)
                )
                if not np.array_equal(original, reproduced):
                    raise ValueError("Predicciones distintas al recargar el modelo")
                predictions.to_parquet(folder / "predictions.parquet")
                targets.to_frame().to_parquet(folder / "targets.parquet")
                write_json(folder / "diagnostics.json", diagnostics)
                pd.Series(
                    model.feature_importances_,
                    index=window.train_features.columns,
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
            "spot-iteration-10-regression",
        )
        click.echo(f"MLflow run: {run_id}")
    click.echo(f"Decisión: {decisions}. Artifacts: {output}")
    return report


@click.command()
@click.option(
    "--dataset", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--output", type=click.Path(file_okay=False, path_type=Path))
@click.option("--tracking-uri", default="http://localhost:5000", envvar="MLFLOW_TRACKING_URI")
@click.option("--no-mlflow", is_flag=True)
def main(dataset, output, tracking_uri, no_mlflow):
    load_dotenv(ROOT / ".env", override=False)
    output = output or ROOT / "data/experiments" / (
        "iteration-10-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    try:
        run_iteration(dataset, output, None if no_mlflow else tracking_uri)
    except Exception as exc:
        raise click.ClickException(f"Iteración 10 incompleta: {exc}; artifacts: {output}") from exc


if __name__ == "__main__":
    main()
