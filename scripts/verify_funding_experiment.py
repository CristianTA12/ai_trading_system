"""Read-only verification of completed iteration 11 artifacts; never trains."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtesting.engine import BacktestResult
from src.backtesting.evaluator import FOLDS, SEEDS, SeedInput, evaluate_all, verdict_to_dict
from src.backtesting.policies import policy_metrics
from src.features.funding import FUNDING_COLUMNS
from src.training.regression_experiment import fold_result


def verify(output: Path) -> dict:
    recipe = json.loads((output / "protocol.json").read_text())
    assert not recipe["test_evaluated"] and not recipe["validation_2024_evaluated"]
    assert recipe["availability_is_assumption"]
    assert recipe["seeds"] == list(SEEDS)
    assert recipe["folds"] == list(FOLDS)
    features = pd.read_parquet(output / "funding_features.parquet")
    alignment = pd.read_parquet(output / "funding_alignment.parquet")
    assert len(features.columns) == 23
    assert features.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
    eligible = alignment.dropna(subset=FUNDING_COLUMNS)
    assert (eligible.assumed_available_at < eligible.index).all()
    assert ((eligible.index - eligible.event_time) <= pd.Timedelta(hours=8, minutes=15)).all()
    pd.testing.assert_frame_equal(features[FUNDING_COLUMNS], eligible[FUNDING_COLUMNS])
    metadata = json.loads((output / "funding_metadata.json").read_text())
    assert (
        hashlib.sha256((output / "funding_features.parquet").read_bytes()).hexdigest()
        == metadata["features_sha256"]
    )
    comparison = pd.read_csv(output / "comparison.csv")
    assert len(comparison) == 128  # 120 strategy backtests + eight benchmarks
    models = list(output.glob("seed_*/*/*/model.ubj"))
    assert len(models) == 40

    def read_result(folder, fold, seed, arm, scenario):
        eq, fills, trades = (
            pd.read_parquet(folder / f"{name}.parquet") for name in ("equity", "fills", "trades")
        )
        result = BacktestResult(eq, fills, trades, float((eq.quantity.iloc[1:] > 0).mean()))
        metrics = policy_metrics(result)
        select = (
            (comparison.fold == fold) & (comparison.arm == arm) & (comparison.scenario == scenario)
        )
        select &= comparison.seed.isna() if seed is None else comparison.seed.eq(seed)
        rows = comparison.loc[select]
        assert len(rows) == 1
        for metric in (
            "total_return",
            "max_drawdown",
            "sharpe",
            "trades",
            "fees_paid",
            "mean_trade_bps",
        ):
            actual, saved = metrics[metric], rows.iloc[0][metric]
            assert (actual is None and pd.isna(saved)) or np.isclose(
                actual, saved, rtol=1e-10, atol=1e-12
            )
        return fold_result(fold, result, metrics)

    benchmarks = {
        fold: read_result(output / "benchmarks" / fold / "buy_hold", fold, None, "buy_hold", "base")
        for fold in FOLDS
    }
    decisions = {}
    for arm in ("funding", "v1_matched"):
        inputs = []
        for seed in SEEDS:
            scenarios = {"base": {}, "stress": {}}
            for fold in FOLDS:
                folder = output / f"seed_{seed}" / fold / arm
                predictions = pd.read_parquet(folder / "predictions.parquet")
                paired_arm = "v1_matched" if arm == "funding" else "funding"
                paired = pd.read_parquet(folder.parent / paired_arm / "predictions.parquet")
                assert predictions.index.equals(paired.index)
                pd.testing.assert_series_equal(predictions.actual_return, paired.actual_return)
                for scenario in ("gross", "base", "stress"):
                    result = read_result(folder / scenario, fold, seed, arm, scenario)
                    assert result.equity_curve.index.equals(benchmarks[fold].equity_curve.index)
                    if scenario != "gross":
                        scenarios[scenario][fold] = result
            inputs.append(SeedInput(seed, scenarios["base"], scenarios["stress"], benchmarks))
        verdict = verdict_to_dict(evaluate_all(inputs))
        saved = json.loads((output / f"{arm}_verdict.json").read_text())
        assert verdict == saved
        decisions[arm] = {"passes": verdict["passes"], "seeds_passing": verdict["seeds_passing"]}
    return {
        "verified": True,
        "models": len(models),
        "strategy_backtests": 120,
        "paired_predictions": True,
        "decision": decisions,
        "test_evaluated": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.output), indent=2))
