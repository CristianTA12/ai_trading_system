"""Iteration 14: preregistered 75bp classes with an exactly reproduced 100bp control."""

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, replace
from importlib.metadata import version
from pathlib import Path

import click
import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from scripts.verify_four_hour_experiment import verify
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
from src.backtesting.regime_gate import daily_regime, gated_targets
from src.models.xgboost.classifier import ModelConfig, fit_predict
from src.models.xgboost.four_hour import HORIZON, four_hour_labels, paired_horizon_folds
from src.training.four_hour_experiment import DATASET, ROOT
from src.training.regression_experiment import fold_result, plot_curves, save_result

PREREGISTRATION = "c1b84b3"
SOURCE = ROOT / "data/experiments/iteration-13-20260930-four-hour"
CANDIDATE = "threshold_75_regime"
CONTROL = "threshold_100_regime"
ARMS = (CANDIDATE, CONTROL)


def assert_control_predictions(model, window, pred):
    pd.testing.assert_index_equal(window.validation_features.index, pred.index)
    np.testing.assert_array_equal(
        model.predict_proba(window.validation_features),
        pred[["p_down", "p_neutral", "p_up"]].to_numpy(),
    )
    np.testing.assert_array_equal(window.validation_returns, pred.actual_return)
    np.testing.assert_array_equal(pred.label_end, pred.index + HORIZON)


def assert_control_result(result, folder):
    for name in ("equity", "fills", "trades"):
        pd.testing.assert_frame_equal(
            getattr(result, name), pd.read_parquet(folder / f"{name}.parquet"), check_exact=True
        )


def run_iteration(output, tracking_uri):
    docs = ["docs/iteration-14-protocol.md", "docs/risk-return-v1.yaml"]
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
        raise ValueError("Commit implementation before training")
    subprocess.check_call(
        ["git", "ls-files", "--error-unmatch", str(Path(__file__).relative_to(ROOT))],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
    )
    for name in docs:
        registered = subprocess.check_output(["git", "show", f"{PREREGISTRATION}:{name}"], cwd=ROOT)
        assert registered.replace(b"\r\n", b"\n") == (ROOT / name).read_bytes().replace(
            b"\r\n", b"\n"
        )
    assert criterion_sha256() == "12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a"
    assert (
        hashlib.sha256((DATASET / "metadata.json").read_bytes()).hexdigest()
        == "a6a80da91f7956a49b5641038ae047b5422fba800a60fa1c7df23c7fd2b42c35"
    )
    source_recipe = json.loads((SOURCE / "protocol.json").read_text())
    for library, recorded in source_recipe["libraries"].items():
        assert version(library) == recorded, f"Library mismatch: {library}"
    click.echo("Verifying frozen iteration 13 before training")
    source_verification = verify(SOURCE)
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
    coverage = pd.read_csv(SOURCE / "coverage.csv").set_index("fold")
    controls = {}
    # All 20 controls are checked before the first candidate is trained.
    for name, (_, short, window) in zip(FOLDS, folds, strict=True):
        train = pd.DataFrame(
            {
                "return_15m": short.train_returns,
                "return_4h": window.train_returns,
                "label_end_4h": window.train_features.index + HORIZON,
            }
        )
        pd.testing.assert_frame_equal(
            train, pd.read_parquet(SOURCE / "folds" / name / "train_rows.parquet"), check_exact=True
        )
        assert len(window.train_features) == coverage.loc[name, "train_rows"]
        assert len(window.validation_features) == coverage.loc[name, "prediction_rows"]
        assert (
            coverage.loc[name, ["train_coverage", "prediction_coverage", "regime_coverage"]].min()
            >= 0.95
        )
        for seed in SEEDS:
            folder = SOURCE / f"seed_{seed}" / name / "four_hour"
            pred = pd.read_parquet(folder / "predictions.parquet")
            model = XGBClassifier()
            model.load_model(folder / "model.ubj")
            assert_control_predictions(model, window, pred)
            controls[seed, name] = pred
    source_paths = [
        SOURCE / "protocol.json",
        SOURCE / "coverage.csv",
        SOURCE / "comparison.csv",
        SOURCE / "four_hour_labels.parquet",
        SOURCE / "regime.parquet",
        SOURCE / "four_hour_regime_verdict.json",
    ]
    source_paths += list((SOURCE / "folds").rglob("*.parquet"))
    for seed in SEEDS:
        for name in FOLDS:
            folder = SOURCE / f"seed_{seed}" / name
            source_paths += list((folder / "four_hour").glob("*"))
            source_paths += list((folder / "four_hour_regime").rglob("*.parquet"))
    source_hashes = {
        str(p.relative_to(SOURCE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths
    }
    output.mkdir(parents=True, exist_ok=False)
    for name in docs:
        shutil.copyfile(ROOT / name, output / Path(name).name)
    for name in ("coverage.csv", "four_hour_labels.parquet", "regime.parquet"):
        shutil.copyfile(SOURCE / name, output / name)
    shutil.copytree(SOURCE / "folds", output / "folds")
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
            "candidate": CANDIDATE,
            "control": CONTROL,
            "criterion_sha256": criterion_sha256(),
            "models": {
                CANDIDATE: asdict(ModelConfig(threshold=0.0075)),
                CONTROL: asdict(ModelConfig(threshold=0.01)),
            },
            "source_experiment": str(SOURCE),
            "source_sha256": source_hashes,
            "source_verification": source_verification,
            "seeds": SEEDS,
            "folds": FOLDS,
            "libraries": source_recipe["libraries"],
            "dataset_metadata": data.metadata,
            "execution": {k: asdict(v) for k, v in scenarios.items()},
            "code_sha256": {
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT / "src").rglob("*.py"))
            },
            "test_evaluated": False,
            "validation_2024_evaluated": False,
        },
    )
    rows, logged, benchmarks = [], {}, {}

    def evaluate(folder, bars, targets, seed, name, arm, scenario):
        result = run_backtest(bars, targets, scenarios[scenario])
        if arm == CONTROL:
            assert_control_result(
                result, SOURCE / f"seed_{seed}" / name / "four_hour_regime" / scenario
            )
        metrics = policy_metrics(result)
        save_result(folder, result)
        rows.append({"seed": seed, "fold": name, "arm": arm, "scenario": scenario, **metrics})
        logged[f"{seed}.{name}.{arm}.{scenario}"] = {
            k: metrics[k] for k in ("total_return", "sharpe", "max_drawdown", "trades", "exposure")
        }
        return fold_result(name, result, metrics)

    for name, (_, _, window) in zip(FOLDS, folds, strict=True):
        for arm, target in (("buy_hold", 1), ("cash", 0)):
            fr = evaluate(
                output / "benchmarks" / name / arm / "base",
                window.validation_bars,
                pd.Series(target, index=window.validation_bars.index),
                None,
                name,
                arm,
                "base",
            )
            if arm == "buy_hold":
                benchmarks[name] = fr
    inputs = {arm: [] for arm in ARMS}
    for seed in SEEDS:
        results = {arm: {scenario: {} for scenario in scenarios} for arm in ARMS}
        for name, (_, _, window) in zip(FOLDS, folds, strict=True):
            click.echo(f"Training seed={seed} fold={name}")
            fold_dir = output / f"seed_{seed}" / name
            folder = fold_dir / "model_75"
            folder.mkdir(parents=True)
            model, pred, diagnostics = fit_predict(window, ModelConfig(seed=seed, threshold=0.0075))
            model.save_model(folder / "model.ubj")
            restored = XGBClassifier()
            restored.load_model(folder / "model.ubj")
            pred["actual_return"], pred["label_end"] = (
                window.validation_returns,
                pred.index + HORIZON,
            )
            assert_control_predictions(restored, window, pred)
            pred.to_parquet(folder / "predictions.parquet")
            write_json(folder / "classification.json", diagnostics)
            pd.Series(
                model.feature_importances_, index=window.train_features.columns, name="importance"
            ).to_csv(folder / "feature_importance.csv")
            shutil.copytree(SOURCE / f"seed_{seed}" / name / "four_hour", fold_dir / "model_100")
            for arm, predictions in ((CANDIDATE, pred), (CONTROL, controls[seed, name])):
                folder = fold_dir / arm
                folder.mkdir()
                targets = gated_targets(
                    window.validation_bars.index, predictions, gate.allow_long, 240
                )
                targets.to_frame().to_parquet(folder / "targets.parquet")
                for scenario in scenarios:
                    fr = evaluate(
                        folder / scenario,
                        window.validation_bars,
                        targets,
                        seed,
                        name,
                        arm,
                        scenario,
                    )
                    results[arm][scenario][name] = fr
                    if scenario == "base":
                        click.echo(
                            f"  {arm}: return={fr.net_return:.2%} DD={fr.max_drawdown:.2%} trades={fr.n_trades}"
                        )
            pd.DataFrame(rows).to_csv(output / "comparison.csv", index=False)
        for arm in ARMS:
            inputs[arm].append(
                SeedInput(seed, results[arm]["base"], results[arm]["stress"], benchmarks)
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
                f"Iteration 14, seed {seed}, {arm}",
            )
    decisions = {}
    for arm in ARMS:
        verdict = evaluate_all(inputs[arm])
        save_verdict(verdict, output / f"{arm}_verdict.json")
        decisions[arm] = {"passes": verdict.passes, "seeds_passing": verdict.seeds_passing}
    assert json.loads((output / f"{CONTROL}_verdict.json").read_text()) == json.loads(
        (SOURCE / "four_hour_regime_verdict.json").read_text()
    )
    for name, digest in source_hashes.items():
        assert hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == digest
    report = {
        "decision": decisions,
        "models_trained": 20,
        "control_models_reused": 20,
        "backtests": len(rows),
        "control_exactly_reproduced": True,
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
            "spot-iteration-14-threshold",
        )
    click.echo(str(report))


@click.command()
@click.option("--output", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--tracking-uri", default="http://localhost:5000")
def main(output, tracking_uri):
    run_iteration(output, tracking_uri)


if __name__ == "__main__":
    main()
