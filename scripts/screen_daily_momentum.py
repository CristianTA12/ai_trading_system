"""Preregistered deterministic architecture screen; never a promotion verdict."""

import hashlib
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtesting.daily_momentum import daily_momentum
from src.backtesting.dataset import load_dataset
from src.backtesting.engine import ExecutionConfig, run_backtest
from src.backtesting.evaluator import FOLDS, SeedInput, criterion_sha256, evaluate_seed
from src.backtesting.experiment import track_results, write_json
from src.backtesting.policies import policy_metrics
from src.backtesting.regime_gate import daily_regime
from src.training.four_hour_experiment import DATASET
from src.training.regression_experiment import fold_result, save_result
from src.training.walk_forward import FOLD_BOUNDARIES

PROTOCOL = Path("docs/daily-momentum-screen-protocol.md")
PREREGISTRATION = "698b838"
OUTPUT = Path("data/experiments/daily-momentum-screen-20261008")


def scalar_check(bars, signal):
    """Independent calendar arithmetic: no rolling windows or as-of joins."""
    close_map = bars.close.to_dict()
    cache = {}
    for timestamp, row in signal.iterrows():
        day = timestamp.floor("D") - pd.Timedelta(days=1)
        if timestamp == timestamp.floor("D"):
            day -= pd.Timedelta(days=1)
        if day not in cache:
            values = [
                close_map.get(day - pd.Timedelta(days=i) + pd.Timedelta(hours=23, minutes=45))
                for i in range(8)
            ]
            valid = all(value is not None for value in values)
            cache[day] = (valid, values[0] / values[7] - 1 if valid else np.nan)
        valid, momentum = cache[day]
        if bool(row.valid) != valid or int(row.target_position) != int(valid and momentum > 0):
            raise ValueError(f"Independent signal mismatch at {timestamp}")
        if valid and not np.isclose(row.momentum_7d, momentum, rtol=0, atol=1e-15):
            raise ValueError("Momentum mismatch")


def main():
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--", "src", "scripts", "tests", str(PROTOCOL)]
    ).strip():
        raise ValueError("Commit implementation before evaluation")
    registered = subprocess.check_output(
        ["git", "show", f"{PREREGISTRATION}:{PROTOCOL.as_posix()}"]
    )
    assert registered.replace(b"\r\n", b"\n") == PROTOCOL.read_bytes().replace(b"\r\n", b"\n")
    assert criterion_sha256() == "12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a"
    assert (
        hashlib.sha256((DATASET / "metadata.json").read_bytes()).hexdigest()
        == "a6a80da91f7956a49b5641038ae047b5422fba800a60fa1c7df23c7fd2b42c35"
    )
    data = load_dataset(DATASET, train_only=True)
    bars = data.train_bars
    assert bars.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
    decisions = bars.index[bars.index >= pd.Timestamp("2022-01-01", tz="UTC")]
    signal = daily_momentum(bars, decisions)
    scalar_check(bars, signal)
    gate = daily_regime(bars, decisions)
    OUTPUT.mkdir(parents=True, exist_ok=False)
    (OUTPUT / PROTOCOL.name).write_bytes(PROTOCOL.read_bytes())
    signal.to_parquet(OUTPUT / "daily_signal.parquet")
    gate.to_parquet(OUTPUT / "regime.parquet")
    config = ExecutionConfig()
    scenarios = {
        "gross": replace(config, maker_fee=0, taker_fee=0, slippage=0),
        "base": config,
        "stress": replace(config, slippage=0.0002),
    }
    rows, results = [], {}
    for fold, start, stop in zip(FOLDS, FOLD_BOUNDARIES[:-1], FOLD_BOUNDARIES[1:], strict=True):
        subset = bars.loc[(bars.index >= start) & (bars.index < stop)]
        targets = {
            "momentum_7d": signal.target_position.loc[subset.index],
            "regime_only": gate.allow_long.loc[subset.index].astype(int),
            "buy_hold": pd.Series(1, index=subset.index),
            "cash": pd.Series(0, index=subset.index),
        }
        pd.DataFrame(targets).to_parquet(OUTPUT / f"targets_{fold.replace(' ', '_')}.parquet")
        for arm, target in targets.items():
            for scenario, execution in scenarios.items():
                result = run_backtest(subset, target, execution)
                metrics = policy_metrics(result)
                folder = OUTPUT / fold.replace(" ", "_") / arm / scenario
                save_result(folder, result)
                write_json(folder / "metrics.json", metrics)
                results[fold, arm, scenario] = fold_result(fold, result, metrics)
                rows.append({"fold": fold, "arm": arm, "scenario": scenario, **metrics})
        print(f"Completed {fold}", flush=True)
    summaries = {}
    for arm in targets:
        verdict = asdict(
            evaluate_seed(
                SeedInput(
                    42,
                    {f: results[f, arm, "base"] for f in FOLDS},
                    {f: results[f, arm, "stress"] for f in FOLDS},
                    {f: results[f, "buy_hold", "base"] for f in FOLDS},
                )
            )
        )
        verdict.pop("seed")
        verdict["economic_gates_pass"] = verdict.pop("all_pass")
        summaries[arm] = verdict
    pd.DataFrame(rows).to_csv(OUTPUT / "comparison.csv", index=False)
    write_json(OUTPUT / "economic_gates.json", summaries)
    write_json(
        OUTPUT / "protocol.json",
        {
            "preregistration_commit": PREREGISTRATION,
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "criterion_sha256": criterion_sha256(),
            "dataset_metadata": data.metadata,
            "execution": {k: asdict(v) for k, v in scenarios.items()},
            "source_sha256": {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for root in ("src", "scripts")
                for p in sorted(Path(root).rglob("*.py"))
            },
            "backtests": 48,
            "models_trained": 0,
            "seeds": [],
            "promoted": False,
            "stability_gate": "not_applicable_not_satisfied",
            "test_evaluated": False,
            "validation_2024_evaluated": False,
            "independent_signal_check": True,
            "signal_rows_verified": len(signal),
        },
    )
    track_results(
        OUTPUT,
        summaries,
        {"partition": "internal_2022_2023", "promoted": False, "models_trained": 0},
        "http://localhost:5000",
        "daily-momentum-architecture-screen",
    )
    print(summaries["momentum_7d"], flush=True)


if __name__ == "__main__":
    main()
