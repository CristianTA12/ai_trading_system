"""Recompute metrics and verdicts from saved iteration-19 artifacts, no simulation."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtesting.engine import BacktestResult
from src.backtesting.evaluator import FOLDS, SEEDS, SeedInput, evaluate_all, verdict_to_dict
from src.backtesting.policies import policy_metrics
from src.training.regression_experiment import fold_result


def verify(output):
    manifest = json.loads((output / "final_manifest.json").read_text())["files_sha256"]
    assert {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()} == set(
        manifest
    ) | {"final_manifest.json"}
    for name, digest in manifest.items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    table = pd.read_csv(output / "comparison.csv")
    assert len(table) == 188
    benchmarks = {}
    results = {}
    for row in table.itertuples():
        root = (
            output / "benchmarks" / row.fold / row.arm
            if pd.isna(row.seed)
            else output / f"seed_{int(row.seed)}" / row.fold / row.arm
        )
        folder = root / row.scenario
        targets = (
            pd.read_parquet(root / "targets.parquet").target_position
            if not pd.isna(row.seed)
            else None
        )
        exposure = float(targets.mean()) if targets is not None else float(row.arm == "buy_hold")
        result = BacktestResult(
            *(
                pd.read_parquet(folder / f"{kind}.parquet")
                for kind in ("equity", "fills", "trades")
            ),
            exposure,
        )
        if targets is not None:
            assert targets.index.equals(result.equity.index[1:] - pd.Timedelta(minutes=15))
            np.testing.assert_array_equal(
                result.equity.quantity.iloc[1:-1].gt(0).to_numpy(),
                targets.iloc[:-1].astype(bool).to_numpy(),
            )
        metrics = policy_metrics(result)
        for key, actual in metrics.items():
            saved = getattr(row, key)
            assert (actual is None and pd.isna(saved)) or np.isclose(
                actual, saved, rtol=1e-10, atol=1e-12
            ), (row.arm, row.fold, key)
        fr = fold_result(row.fold, result, metrics)
        if row.arm == "buy_hold":
            benchmarks[row.fold] = fr
        elif row.arm != "cash":
            results[row.arm, int(row.seed), row.scenario, row.fold] = fr
    for arm in ("four_hour_regime", "four_hour_down", "four_hour_hysteresis"):
        verdict = evaluate_all(
            [
                SeedInput(
                    seed,
                    {fold: results[arm, seed, "base", fold] for fold in FOLDS},
                    {fold: results[arm, seed, "stress", fold] for fold in FOLDS},
                    benchmarks,
                )
                for seed in SEEDS
            ]
        )
        assert verdict_to_dict(verdict) == json.loads((output / f"{arm}_verdict.json").read_text())
    return {
        "verified": True,
        "manifest_files": len(manifest),
        "metrics_recomputed": 188,
        "verdicts_recomputed": 3,
        "new_backtests": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.output), indent=2))
