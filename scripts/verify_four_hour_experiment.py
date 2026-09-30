"""Read-only verification of iteration 13 labels, paired models, policies and verdicts."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtesting.dataset import load_dataset
from src.backtesting.engine import STEP, BacktestResult
from src.backtesting.evaluator import FOLDS, SEEDS, SeedInput, evaluate_all, verdict_to_dict
from src.backtesting.policies import policy_metrics
from src.training.regression_experiment import fold_result

ROOT = Path(__file__).resolve().parents[1]


def verify(output: Path) -> dict:
    recipe = json.loads((output / "protocol.json").read_text())
    assert not recipe["test_evaluated"] and not recipe["validation_2024_evaluated"]
    for name, digest in recipe["artifact_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    data = load_dataset(
        ROOT / "data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z",
        train_only=True,
    )
    labels = pd.read_parquet(output / "four_hour_labels.parquet")
    gate = pd.read_parquet(output / "regime.parquet")
    horizon = pd.Timedelta(hours=4)
    assert (labels.label_end == labels.index + horizon).all()
    # Independent label reconstruction by timestamp lookup, not row shifts.
    bars = data.train_bars
    expected_index = data.train_features.index
    complete = np.ones(len(expected_index), dtype=bool)
    for offset in range(16):
        complete &= (expected_index + offset * STEP).isin(bars.index)
    assert labels.index.equals(expected_index[complete])
    expected_return = (
        bars.close.reindex(labels.index + 15 * STEP).to_numpy()
        / bars.open.reindex(labels.index).to_numpy()
        - 1
    )
    np.testing.assert_array_equal(labels.target_return.to_numpy(), expected_return)
    table = pd.read_csv(output / "comparison.csv")
    assert len(table) == 200 and len(list(output.glob("seed_*/*/*/model.ubj"))) == 40
    coverage = pd.read_csv(output / "coverage.csv").set_index("fold")
    boundaries = pd.to_datetime(
        ["2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01"], utc=True
    )
    arms = ("four_hour_regime", "four_hour_control", "fifteen_min_regime")

    def read(folder, fold, seed, arm, scenario):
        eq, fills, trades = (
            pd.read_parquet(folder / f"{name}.parquet") for name in ("equity", "fills", "trades")
        )
        result = BacktestResult(eq, fills, trades, 0.0)
        metrics = policy_metrics(result)
        row = table.loc[
            table.fold.eq(fold)
            & table.arm.eq(arm)
            & table.scenario.eq(scenario)
            & (table.seed.isna() if seed is None else table.seed.eq(seed))
        ]
        assert len(row) == 1
        for key in (
            "total_return",
            "sharpe",
            "max_drawdown",
            "trades",
            "fees_paid",
            "mean_trade_bps",
        ):
            actual, saved = metrics[key], row.iloc[0][key]
            assert (actual is None and pd.isna(saved)) or np.isclose(
                actual, saved, rtol=1e-10, atol=1e-12
            )
        if arm.endswith("regime") or arm == "regime_only":
            permitted = gate.allow_long.reindex(eq.index - STEP, fill_value=False).to_numpy()
            assert not ((eq.quantity.to_numpy() > 0) & ~permitted).any()
        return fold_result(fold, result, metrics)

    benchmarks = {}
    for fold in FOLDS:
        for arm in ("buy_hold", "cash", "regime_only"):
            for scenario in ("gross", "base", "stress") if arm == "regime_only" else ("base",):
                fr = read(output / "benchmarks" / fold / arm / scenario, fold, None, arm, scenario)
                if arm == "buy_hold":
                    benchmarks[fold] = fr
    inputs = {arm: [] for arm in arms}
    missing_outcome_rows = 0
    for seed in SEEDS:
        results = {arm: {scenario: {} for scenario in ("base", "stress")} for arm in arms}
        for i, fold in enumerate(FOLDS):
            folder = output / f"seed_{seed}" / fold
            train = pd.read_parquet(output / "folds" / fold / "train_rows.parquet")
            expected_train = labels.index[labels.index + horizon < boundaries[i]]
            assert train.index.equals(expected_train)
            np.testing.assert_array_equal(train.return_4h, labels.loc[train.index, "target_return"])
            np.testing.assert_array_equal(train.return_15m, data.train_returns.loc[train.index])
            assert (train.label_end_4h < boundaries[i]).all()
            pred = {
                name: pd.read_parquet(folder / name / "predictions.parquet")
                for name in ("four_hour", "fifteen_min")
            }
            index = data.train_features.index
            expected = index[(index >= boundaries[i]) & (index + horizon < boundaries[i + 1])]
            assert pred["four_hour"].index.equals(expected) and pred["fifteen_min"].index.equals(
                expected
            )
            np.testing.assert_allclose(
                pred["four_hour"].actual_return,
                labels.target_return.reindex(expected),
                rtol=0,
                atol=0,
                equal_nan=True,
            )
            np.testing.assert_array_equal(
                pred["fifteen_min"].actual_return, data.train_returns.loc[expected]
            )
            assert (
                pred["four_hour"].actual_return.notna().sum()
                == coverage.loc[fold, "scored_4h_rows"]
            )
            missing_outcome_rows += int(pred["four_hour"].actual_return.isna().sum())
            for arm in arms:
                p = pred["fifteen_min" if arm == "fifteen_min_regime" else "four_hour"]
                minimum = pd.Timedelta(minutes=60 if arm == "fifteen_min_regime" else 240)
                probabilities = p[["p_down", "p_neutral", "p_up"]]
                entries = pd.Series(
                    (probabilities.to_numpy().argmax(axis=1) == 2) & (p.p_up.to_numpy() >= 0.5),
                    index=p.index,
                )
                targets = pd.read_parquet(folder / arm / "targets.parquet").target_position
                active, entry_at, expected_targets = False, None, []
                for timestamp in targets.index:
                    blocked = arm != "four_hour_control" and not gate.at[timestamp, "allow_long"]
                    if blocked or timestamp not in entries.index:
                        active = False
                    elif active:
                        if timestamp - entry_at >= minimum and not entries.at[timestamp]:
                            active = False
                    elif entries.at[timestamp]:
                        active, entry_at = True, timestamp
                    expected_targets.append(int(active))
                np.testing.assert_array_equal(targets, expected_targets)
                for scenario in ("gross", "base", "stress"):
                    fr = read(folder / arm / scenario, fold, seed, arm, scenario)
                    assert fr.equity_curve.index.equals(benchmarks[fold].equity_curve.index)
                    if scenario != "gross":
                        results[arm][scenario][fold] = fr
        for arm in arms:
            inputs[arm].append(
                SeedInput(seed, results[arm]["base"], results[arm]["stress"], benchmarks)
            )
    decisions = {}
    for arm in arms:
        verdict = verdict_to_dict(evaluate_all(inputs[arm]))
        assert verdict == json.loads((output / f"{arm}_verdict.json").read_text())
        decisions[arm] = {"passes": verdict["passes"], "seeds_passing": verdict["seeds_passing"]}
    return {
        "verified": True,
        "models": 40,
        "backtests": 200,
        "paired_rows": True,
        "labels_reconstructed_by_timestamp": True,
        "independent_policy_replay": True,
        "unscorable_predictions_retained_across_seeds": missing_outcome_rows,
        "decision": decisions,
        "test_evaluated": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.output), indent=2))
