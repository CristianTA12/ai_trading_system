"""Iteration 17: paired v1/flow training under a fixed delivery assumption."""

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

from scripts.verify_aggressor_preparation import verify as verify_preparation
from src.backtesting.dataset import load_dataset
from src.backtesting.engine import ExecutionConfig, run_backtest
from src.backtesting.evaluator import (
    FOLDS,
    SEEDS,
    SeedInput,
    criterion_sha256,
    evaluate_all,
    save_verdict,
)
from src.backtesting.experiment import track_results, write_json
from src.backtesting.policies import policy_metrics
from src.backtesting.regime_gate import daily_regime, gated_targets
from src.features.aggressor_flow import FLOW_COLUMNS
from src.models.xgboost.classifier import ModelConfig, fit_predict
from src.models.xgboost.four_hour import HORIZON, four_hour_labels, paired_horizon_folds
from src.training.four_hour_experiment import DATASET, ROOT
from src.training.regression_experiment import fold_result, save_result
from src.training.sp500_experiment import assert_control_predictions

PREREGISTRATION = "a2ebd87"
PREPARATION = ROOT / "data/processed/aggressor-flow-preparation-20261008"
SOURCE = ROOT / "data/experiments/iteration-13-20260930-four-hour"
CANDIDATE, CONTROL = "flow_regime", "v1_regime"
ARMS = (CONTROL, CANDIDATE)


def paired_windows(window, folder):
    selected, extra = {}, {}
    for split, original in (
        ("train", window.train_features),
        ("evaluation", window.validation_features),
    ):
        aligned = pd.read_parquet(folder / f"{split}.parquet")
        pd.testing.assert_index_equal(original.index, aligned.index)
        assert len(original.columns) == 20 and not set(original.columns) & set(FLOW_COLUMNS)
        eligible = aligned.eligible_under_assumption
        assert eligible.mean() >= 0.95
        selected[split] = original.loc[eligible]
        extra[split] = aligned.loc[eligible, FLOW_COLUMNS]
        assert np.isfinite(extra[split].to_numpy()).all()
    control = replace(
        window,
        train_features=selected["train"],
        train_returns=window.train_returns.reindex(selected["train"].index),
        validation_features=selected["evaluation"],
        validation_returns=window.validation_returns.reindex(selected["evaluation"].index),
    )
    candidate = replace(
        control,
        train_features=pd.concat([selected["train"], extra["train"]], axis=1),
        validation_features=pd.concat([selected["evaluation"], extra["evaluation"]], axis=1),
    )
    return {CONTROL: control, CANDIDATE: candidate}


def preparation_hashes():
    return {
        str(p.relative_to(PREPARATION)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in PREPARATION.rglob("*")
        if p.is_file()
    }


def run_iteration(output, tracking_uri):
    docs = ["docs/iteration-17-protocol.md", "docs/risk-return-v1.yaml"]
    assert not subprocess.check_output(
        ["git", "status", "--porcelain", "--", "src", "scripts", "tests", *docs], cwd=ROOT
    ).strip()
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
    libraries = json.loads((SOURCE / "protocol.json").read_text())["libraries"]
    for library, recorded in libraries.items():
        assert version(library) == recorded, library
    click.echo("Verifying preparation, hashes and all scalar feature values")
    verification = verify_preparation(PREPARATION)
    hashes = preparation_hashes()
    data = load_dataset(DATASET, train_only=True)
    labels = four_hour_labels(data.train_bars, data.train_features.index)
    gate = daily_regime(data.train_bars, data.train_bars.index)
    folds = list(paired_horizon_folds(data, labels))
    windows = {
        name: paired_windows(window, PREPARATION / "alignment" / name)
        for name, (_, _, window) in zip(FOLDS, folds, strict=True)
    }
    original_predictions, source_hashes = {}, {}
    for name, (_, _, window) in zip(FOLDS, folds, strict=True):
        index_path = SOURCE / "folds" / name / "train_rows.parquet"
        pd.testing.assert_index_equal(
            window.train_features.index, pd.read_parquet(index_path, columns=[]).index
        )
        assert len(windows[name][CONTROL].train_features) == len(window.train_features)
        for seed in SEEDS:
            path = SOURCE / f"seed_{seed}" / name / "four_hour/predictions.parquet"
            source_hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            original_predictions[seed, name] = pd.read_parquet(path)
    assert [len(windows[f][CONTROL].validation_features) for f in FOLDS] == [
        17360,
        17648,
        17302,
        17648,
    ]
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(PREPARATION, output / "flow_features")
    for name in docs:
        shutil.copyfile(ROOT / name, output / Path(name).name)
    labels.to_parquet(output / "four_hour_labels.parquet")
    gate.to_parquet(output / "regime.parquet")
    for name in FOLDS:
        folder = output / "folds" / name
        folder.mkdir(parents=True)
        window = windows[name][CONTROL]
        pd.DataFrame(
            {
                "return_4h": window.train_returns,
                "label_end_4h": window.train_features.index + HORIZON,
            }
        ).to_parquet(folder / "train_rows.parquet")
    config = ExecutionConfig()
    scenarios = {
        "gross": replace(config, maker_fee=0, taker_fee=0, slippage=0),
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
            "features": FLOW_COLUMNS,
            "conditional_research": True,
            "historical_availability_proven": False,
            "assumed_delivery_margin_minutes": 15,
            "preparation_verification": verification,
            "preparation_sha256": hashes,
            "source_sha256": source_hashes,
            "source_experiment": str(SOURCE),
            "dataset_metadata": data.metadata,
            "criterion_sha256": criterion_sha256(),
            "libraries": libraries,
            "model": asdict(ModelConfig(threshold=0.01)),
            "seeds": SEEDS,
            "folds": FOLDS,
            "execution": {k: asdict(v) for k, v in scenarios.items()},
            "code_sha256": {
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for root in ("src", "scripts")
                for p in sorted((ROOT / root).rglob("*.py"))
            },
            "test_evaluated": False,
            "validation_2024_evaluated": False,
        },
    )
    rows, logged, benchmarks = [], {}, {}

    def evaluate(folder, bars, targets, seed, name, arm, scenario):
        result = run_backtest(bars, targets, scenarios[scenario])
        metrics = policy_metrics(result)
        save_result(folder, result)
        rows.append({"seed": seed, "fold": name, "arm": arm, "scenario": scenario, **metrics})
        logged[f"{seed}.{name}.{arm}.{scenario}"] = {
            k: metrics[k] for k in ("total_return", "sharpe", "max_drawdown", "trades", "exposure")
        }
        return fold_result(name, result, metrics)

    for name in FOLDS:
        bars = windows[name][CONTROL].validation_bars
        for arm, value in (("buy_hold", 1), ("cash", 0)):
            fr = evaluate(
                output / "benchmarks" / name / arm / "base",
                bars,
                pd.Series(value, index=bars.index),
                None,
                name,
                arm,
                "base",
            )
            if arm == "buy_hold":
                benchmarks[name] = fr
    inputs = {arm: [] for arm in ARMS}
    for seed in SEEDS:
        results = {arm: {s: {} for s in scenarios} for arm in ARMS}
        for name in FOLDS:
            for arm in ARMS:
                window = windows[name][arm]
                click.echo(f"Training seed={seed} fold={name} arm={arm}")
                folder = (
                    output
                    / f"seed_{seed}"
                    / name
                    / ("model_flow" if arm == CANDIDATE else "model_v1")
                )
                folder.mkdir(parents=True)
                model, pred, diagnostics = fit_predict(
                    window, ModelConfig(seed=seed, threshold=0.01)
                )
                pred["actual_return"], pred["label_end"] = (
                    window.validation_returns,
                    pred.index + HORIZON,
                )
                model.save_model(folder / "model.ubj")
                restored = XGBClassifier()
                restored.load_model(folder / "model.ubj")
                assert_control_predictions(restored, window, pred)
                if arm == CONTROL:
                    original = original_predictions[seed, name].loc[pred.index]
                    np.testing.assert_array_equal(
                        pred[["p_down", "p_neutral", "p_up"]],
                        original[["p_down", "p_neutral", "p_up"]],
                    )
                pred.to_parquet(folder / "predictions.parquet")
                write_json(folder / "classification.json", diagnostics)
                pd.Series(
                    model.feature_importances_,
                    index=window.train_features.columns,
                    name="importance",
                ).to_csv(folder / "feature_importance.csv")
                folder = output / f"seed_{seed}" / name / arm
                folder.mkdir()
                targets = gated_targets(window.validation_bars.index, pred, gate.allow_long, 240)
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
                click.echo(f"Completed seed={seed} fold={name} arm={arm}")
            pd.DataFrame(rows).to_csv(output / "comparison.csv", index=False)
        for arm in ARMS:
            inputs[arm].append(
                SeedInput(seed, results[arm]["base"], results[arm]["stress"], benchmarks)
            )
    decisions = {}
    for arm in ARMS:
        verdict = evaluate_all(inputs[arm])
        save_verdict(verdict, output / f"{arm}_verdict.json")
        decisions[arm] = {"passes": verdict.passes, "seeds_passing": verdict.seeds_passing}
    assert hashes == preparation_hashes()
    for path, expected in source_hashes.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
    report = {
        "decision": decisions,
        "models_trained": 40,
        "backtests": len(rows),
        "control_predictions_reproduced_on_common_rows": True,
        "conditional_research": True,
        "historical_availability_proven": False,
        "test_evaluated": False,
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
                "conditional_research": True,
                "test_evaluated": False,
            },
            tracking_uri,
            "spot-iteration-17-aggressor-flow",
        )
    click.echo(str(report))


@click.command()
@click.option("--output", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--tracking-uri", default="http://localhost:5000")
def main(output, tracking_uri):
    run_iteration(output, tracking_uri)


if __name__ == "__main__":
    main()
