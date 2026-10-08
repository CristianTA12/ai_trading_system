"""Prepare frozen flow features on iteration-13 indices; no outcome or model reads."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.audit_aggressor_flow import MONTHS, RAW, inspect_month
from scripts.prepare_sp500_experiment import FOLDS, SEEDS, SOURCE
from src.features.aggressor_flow import FLOW_COLUMNS, aggregate_flow, align_flow

OUT = Path("data/processed/aggressor-flow-preparation-20261008")
AUDIT = Path("data/external/aggressor-flow-audit-20261008-complete")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def independent_check(frame, bars):
    """Scalar sums by exact timestamps; no feature builder calls."""
    lookup = {t: (v, b) for t, v, b in bars[["volume", "taker_base"]].itertuples()}
    for row in frame.itertuples():
        end = row.Index - pd.Timedelta(minutes=30)
        values = [lookup.get(end - pd.Timedelta(minutes=15 * i)) for i in range(4)]
        short = (
            (2 * values[0][1] / values[0][0] - 1)
            if values[0] is not None and values[0][0] > 0
            else np.nan
        )
        total = sum(v[0] for v in values) if all(v is not None for v in values) else 0
        long = 2 * sum(v[1] for v in values) / total - 1 if total > 0 else np.nan
        assert np.allclose(
            [short, long],
            [row.flow_imbalance_15m, row.flow_imbalance_1h],
            atol=1e-14,
            rtol=0,
            equal_nan=True,
        )
        assert row.eligible_under_assumption == bool(np.isfinite([short, long]).all())


def main():
    audit = pd.read_csv(AUDIT / "local_months.csv").set_index("month")
    frames, hashes = [], {}
    for month in MONTHS:
        path = RAW / f"BTCUSDT-1m-{month}.zip"
        report, frame = inspect_month(month)
        assert report["sha256"] == audit.loc[month, "sha256"]
        frames.append(frame)
        hashes[str(path)] = report["sha256"]
    bars = aggregate_flow(pd.concat(frames))
    OUT.mkdir(parents=True, exist_ok=False)
    bars.to_parquet(OUT / "flow_bars.parquet")
    rows, index_hashes = [], {}
    for fold in FOLDS:
        for split, path in (
            ("train", SOURCE / "folds" / fold / "train_rows.parquet"),
            ("evaluation", SOURCE / "seed_42" / fold / "four_hour" / "predictions.parquet"),
        ):
            index = pd.read_parquet(path, columns=[]).index
            assert index.max() < pd.Timestamp("2024-01-01", tz="UTC")
            index_hashes[str(path)] = digest(path)
            if split == "evaluation":
                for seed in SEEDS:
                    other = SOURCE / f"seed_{seed}" / fold / "four_hour" / "predictions.parquet"
                    pd.testing.assert_index_equal(index, pd.read_parquet(other, columns=[]).index)
                    index_hashes[str(other)] = digest(other)
            frame = align_flow(index, bars)
            independent_check(frame, bars)
            folder = OUT / "alignment" / fold
            folder.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(folder / f"{split}.parquet")
            eligible = frame.eligible_under_assumption
            pd.DataFrame(index=index[eligible]).to_parquet(folder / f"{split}_paired_rows.parquet")
            rows.append(
                {
                    "fold": fold,
                    "split": split,
                    "original_rows": len(index),
                    "eligible_rows": int(eligible.sum()),
                    "coverage": float(eligible.mean()),
                }
            )
            print(rows[-1], flush=True)
    assert all(digest(Path(path)) == value for path, value in hashes.items())
    report = {
        "coverage": rows,
        "features": FLOW_COLUMNS,
        "raw_sha256": hashes,
        "source_index_sha256": index_hashes,
        "independent_scalar_verification": True,
        "verified_rows": sum(row["original_rows"] for row in rows),
        "coverage_requirement_met": all(row["coverage"] >= 0.95 for row in rows),
        "assumed_delivery_margin_minutes": 15,
        "historical_availability_proven": False,
        "models_trained": 0,
        "backtests": 0,
        "test_evaluated": False,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    pd.DataFrame(rows).to_csv(OUT / "coverage.csv", index=False)
    if not report["coverage_requirement_met"]:
        raise ValueError("Coverage below 95%; do not change timing to rescue coverage")


if __name__ == "__main__":
    main()
