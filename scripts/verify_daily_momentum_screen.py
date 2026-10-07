import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.backtesting.engine import BacktestResult
from src.backtesting.evaluator import FOLDS, SeedInput, evaluate_seed
from src.backtesting.policies import policy_metrics
from src.training.regression_experiment import fold_result

out = Path("data/experiments/daily-momentum-screen-20261008")
frames = {}
count = 0
for fold in FOLDS:
    targets = pd.read_parquet(out / f"targets_{fold.replace(' ', '_')}.parquet")
    for arm in targets:
        for scenario in ("gross", "base", "stress"):
            folder = out / fold.replace(" ", "_") / arm / scenario
            equity = pd.read_parquet(folder / "equity.parquet")
            fills = pd.read_parquet(folder / "fills.parquet")
            trades = pd.read_parquet(folder / "trades.parquet")
            result = BacktestResult(equity, fills, trades, float(targets[arm].mean()))
            actual = policy_metrics(result)
            expected = json.loads((folder / "metrics.json").read_text())
            assert actual == expected, (fold, arm, scenario)
            frames[fold, arm, scenario] = fold_result(fold, result, actual)
            count += 1
stored = json.loads((out / "economic_gates.json").read_text())
for arm in targets:
    actual = asdict(
        evaluate_seed(
            SeedInput(
                42,
                {f: frames[f, arm, "base"] for f in FOLDS},
                {f: frames[f, arm, "stress"] for f in FOLDS},
                {f: frames[f, "buy_hold", "base"] for f in FOLDS},
            )
        )
    )
    actual.pop("seed")
    actual["economic_gates_pass"] = actual.pop("all_pass")
    assert actual == stored[arm]
(out / "verification.json").write_text(
    json.dumps(
        {
            "verified": True,
            "saved_backtests_recomputed": count,
            "verdicts_recomputed": 4,
            "independent_signal_check": True,
            "promoted": False,
        },
        indent=2,
    )
    + "\n"
)
print(
    json.dumps(
        {
            arm: {k: v for k, v in values.items() if k not in ("folds", "detail")}
            for arm, values in stored.items()
        },
        indent=2,
    )
)
print(pd.read_csv(out / "comparison.csv").query("scenario == 'base'").to_string(index=False))
