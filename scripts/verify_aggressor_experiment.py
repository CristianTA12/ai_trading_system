"""Independently replay policies, metrics and decisions for conditional iteration 17 artifacts."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from scripts.diagnose_2023h1 import class_counts, replay
from scripts.verify_aggressor_preparation import verify as verify_preparation
from src.backtesting.dataset import load_dataset
from src.backtesting.engine import BacktestResult
from src.backtesting.evaluator import FOLDS, SEEDS, SeedInput, evaluate_all, verdict_to_dict
from src.backtesting.policies import policy_metrics
from src.backtesting.regime_gate import daily_regime
from src.features.aggressor_flow import FLOW_COLUMNS
from src.models.xgboost.four_hour import four_hour_labels, paired_horizon_folds
from src.training.aggressor_experiment import paired_windows
from src.training.four_hour_experiment import DATASET
from src.training.regression_experiment import fold_result


def verify(output):
    recipe = json.loads((output / "protocol.json").read_text())
    source = Path(recipe["source_experiment"])
    assert recipe["conditional_research"] and not recipe["historical_availability_proven"]
    assert recipe["features"] == FLOW_COLUMNS
    verify_preparation(output / "flow_features")
    for name, digest in recipe["preparation_sha256"].items():
        assert hashlib.sha256((output / "flow_features" / name).read_bytes()).hexdigest() == digest
    for name, digest in recipe["source_sha256"].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest
    assert not recipe["test_evaluated"] and not recipe["validation_2024_evaluated"]
    data = load_dataset(DATASET, train_only=True)
    calculated_labels = four_hour_labels(data.train_bars, data.train_features.index)
    windows = {
        name: paired_windows(window, output / "flow_features" / "alignment" / name)
        for name, (_, _, window) in zip(
            FOLDS, paired_horizon_folds(data, calculated_labels), strict=True
        )
    }
    gate = pd.read_parquet(output / "regime.parquet").allow_long
    labels = pd.read_parquet(output / "four_hour_labels.parquet")
    pd.testing.assert_frame_equal(labels, calculated_labels, check_exact=True)
    pd.testing.assert_series_equal(
        gate, daily_regime(data.train_bars, data.train_bars.index).allow_long, check_exact=True
    )
    table = pd.read_csv(output / "comparison.csv")
    assert len(table) == 128
    assert len(list(output.glob("seed_*/*/model_*/model.ubj"))) == 40
    candidate, control = recipe["candidate"], recipe["control"]
    inputs = {arm: [] for arm in (candidate, control)}
    reads, missing = 0, 0

    def read(folder, seed, fold, arm, scenario, exposure):
        nonlocal reads
        eq, fills, trades = (
            pd.read_parquet(folder / f"{n}.parquet") for n in ("equity", "fills", "trades")
        )
        metrics = policy_metrics(BacktestResult(eq, fills, trades, exposure))
        row = table.loc[
            table.fold.eq(fold)
            & table.arm.eq(arm)
            & table.scenario.eq(scenario)
            & (table.seed.isna() if seed is None else table.seed.eq(seed))
        ]
        assert len(row) == 1
        for key, value in metrics.items():
            actual = row.iloc[0][key]
            if value is None:
                assert pd.isna(actual)
            else:
                np.testing.assert_allclose(actual, value, rtol=1e-12, atol=1e-12)
        reads += 1
        return fold_result(fold, BacktestResult(eq, fills, trades, exposure), metrics)

    benchmarks = {}
    for fold in FOLDS:
        for arm, exposure in (("buy_hold", 1.0), ("cash", 0.0)):
            fr = read(
                output / "benchmarks" / fold / arm / "base", None, fold, arm, "base", exposure
            )
            if arm == "buy_hold":
                benchmarks[fold] = fr
    for seed in SEEDS:
        results = {arm: {s: {} for s in ("base", "stress")} for arm in inputs}
        for fold in FOLDS:
            folder = output / f"seed_{seed}" / fold
            train = pd.read_parquet(output / "folds" / fold / "train_rows.parquet")
            np.testing.assert_array_equal(train.return_4h, windows[fold][control].train_returns)
            pd.testing.assert_index_equal(train.index, windows[fold][control].train_features.index)
            flow_pred = pd.read_parquet(folder / "model_flow/predictions.parquet")
            v1_pred = pd.read_parquet(folder / "model_v1/predictions.parquet")
            pd.testing.assert_index_equal(flow_pred.index, v1_pred.index)
            np.testing.assert_array_equal(flow_pred.actual_return, v1_pred.actual_return)
            for arm, model_name, pred, threshold in (
                (candidate, "model_flow", flow_pred, 0.01),
                (control, "model_v1", v1_pred, 0.01),
            ):
                model = XGBClassifier()
                model.load_model(folder / model_name / "model.ubj")
                np.testing.assert_array_equal(
                    model.predict_proba(windows[fold][arm].validation_features),
                    pred[["p_down", "p_neutral", "p_up"]].to_numpy(),
                )
                pd.testing.assert_index_equal(
                    pred.index, windows[fold][arm].validation_features.index
                )
                if arm == control:
                    original = pd.read_parquet(
                        source / f"seed_{seed}" / fold / "four_hour/predictions.parquet"
                    ).loc[pred.index]
                    np.testing.assert_array_equal(
                        pred[["p_down", "p_neutral", "p_up"]],
                        original[["p_down", "p_neutral", "p_up"]],
                    )
                names = model.get_booster().feature_names
                assert len(names) == (22 if arm == candidate else 20)
                if arm == candidate:
                    assert names[-2:] == FLOW_COLUMNS
                diagnostics = json.loads((folder / model_name / "classification.json").read_text())
                assert diagnostics["config"]["threshold"] == threshold
                assert diagnostics["config"]["seed"] == seed
                assert diagnostics["train_class_counts"] == class_counts(train.return_4h, threshold)
                assert diagnostics["validation_class_counts"] == class_counts(
                    pred.actual_return, threshold
                )
                np.testing.assert_array_equal(
                    pred.actual_return, labels.target_return.reindex(pred.index)
                )
                assert (pred.label_end == pred.index + pd.Timedelta(hours=4)).all()
                missing += int(pred.actual_return.isna().sum())
                probs = pred[["p_down", "p_neutral", "p_up"]]
                signal = pd.Series(
                    (probs.to_numpy().argmax(axis=1) == 2) & pred.p_up.ge(0.5), index=pred.index
                )
                targets = pd.read_parquet(folder / arm / "targets.parquet").target_position
                expected, entries, _ = replay(targets.index, signal, gate)
                np.testing.assert_array_equal(targets, expected)
                trades = pd.read_parquet(folder / arm / "base/trades.parquet")
                assert entries == trades.entry_time.tolist()
                for scenario in ("gross", "base", "stress"):
                    fr = read(
                        folder / arm / scenario, seed, fold, arm, scenario, float(targets.mean())
                    )
                    pd.testing.assert_index_equal(
                        fr.equity_curve.index, benchmarks[fold].equity_curve.index
                    )
                    if scenario != "gross":
                        results[arm][scenario][fold] = fr
        for arm in inputs:
            inputs[arm].append(
                SeedInput(seed, results[arm]["base"], results[arm]["stress"], benchmarks)
            )
    decisions = {}
    for arm in inputs:
        verdict = verdict_to_dict(evaluate_all(inputs[arm]))
        assert verdict == json.loads((output / f"{arm}_verdict.json").read_text())
        decisions[arm] = {"passes": verdict["passes"], "seeds_passing": verdict["seeds_passing"]}
    assert reads == 128 and missing == 150
    return {
        "verified": True,
        "conditional_research": True,
        "historical_availability_proven": False,
        "backtests": reads,
        "models": 40,
        "control_predictions_reproduced_on_common_rows": True,
        "paired_prediction_rows": True,
        "independent_policy_replay": True,
        "unscorable_predictions_retained": missing,
        "decision": decisions,
        "test_evaluated": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = verify(args.output)
    (args.output / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
