"""Prepare iteration 15 macro rows using indices only: no labels, predictions or training."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from src.features.sp500 import SNAPSHOT_SHA256, SP500_COLUMNS, align_sp500, load_sp500

SOURCE = Path("data/experiments/iteration-13-20260930-four-hour")
SNAPSHOT = Path("data/external/macro-audit-20261006-retry/SP500.csv")
SEEDS = (42, 123, 456, 789, 2026)
FOLDS = ("2022 H1", "2022 H2", "2023 H1", "2023 H2")


def prepare(output):
    closes = load_sp500(SNAPSHOT)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(SNAPSHOT, output / "SP500.csv")
    hashes, rows = {}, []
    for fold in FOLDS:
        for split, path in (
            ("train", SOURCE / "folds" / fold / "train_rows.parquet"),
            ("evaluation", SOURCE / "seed_42" / fold / "four_hour" / "predictions.parquet"),
        ):
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            index = pd.read_parquet(path, columns=[]).index
            if split == "evaluation":
                for seed in SEEDS:
                    other = SOURCE / f"seed_{seed}" / fold / "four_hour" / "predictions.parquet"
                    pd.testing.assert_index_equal(index, pd.read_parquet(other, columns=[]).index)
                    hashes[str(other)] = hashlib.sha256(other.read_bytes()).hexdigest()
            frame = align_sp500(index, closes)
            pd.testing.assert_index_equal(index, frame.index)
            destination = output / "alignment" / fold
            destination.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(destination / f"{split}.parquet")
            eligible = frame.eligible_under_assumption
            # This exact index is shared by candidate and control.
            pd.DataFrame(index=index[eligible]).to_parquet(
                destination / f"{split}_paired_rows.parquet"
            )
            rows.append(
                {
                    "fold": fold,
                    "split": split,
                    "original_rows": len(index),
                    "eligible_rows": int(eligible.sum()),
                    "coverage": float(eligible.mean()),
                    "max_eligible_observation_age_hours": float(
                        frame.loc[eligible, SP500_COLUMNS[2]].max()
                    ),
                }
            )
    pd.DataFrame(rows).to_csv(output / "coverage.csv", index=False)
    report = {
        "coverage": rows,
        "coverage_requirement_met": all(r["coverage"] >= 0.95 for r in rows),
        "original_indices_fully_preserved": all(r["coverage"] == 1 for r in rows),
        "features": SP500_COLUMNS,
        "snapshot_sha256": SNAPSHOT_SHA256,
        "assumptions_accepted_by_user": True,
        "assumed_delay_hours": 48,
        "max_observation_age_hours": 168,
        "strict_asof": True,
        "historical_availability_proven": False,
        "models_trained": 0,
        "backtests_run": 0,
        "test_evaluated": False,
        "source_index_sha256": hashes,
        "code_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), Path("src/features/sp500.py")]
        },
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if "sha256" not in k}, indent=2))
    if not report["coverage_requirement_met"]:
        raise ValueError("Coverage below 95%; stop without changing timing policy")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.output)
