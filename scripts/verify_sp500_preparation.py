"""Independent searchsorted and NumPy verification of prepared SP500 feature rows."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def verify(folder):
    report = json.loads((folder / "report.json").read_text())
    raw = folder / "SP500.csv"
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == report["snapshot_sha256"]
    data = pd.read_csv(raw).dropna(subset=["SP500"])
    dates = pd.DatetimeIndex(pd.to_datetime(data.observation_date, utc=True)).as_unit("ns")
    assert dates.is_unique and dates.is_monotonic_increasing
    assert dates.min() >= pd.Timestamp("2019-11-01", tz="UTC")
    assert dates.max() < pd.Timestamp("2024-01-01", tz="UTC")
    closes = data.SP500.to_numpy()
    returns = np.r_[np.nan, closes[1:] / closes[:-1] - 1]
    distance = np.full(len(closes), np.nan)
    for i in range(19, len(closes)):
        distance[i] = closes[i] / np.mean(closes[i - 19 : i + 1]) - 1
    hour = 3_600_000_000_000
    available = dates.asi8 + 48 * hour
    verified_rows = 0
    for row in report["coverage"]:
        base = folder / "alignment" / row["fold"]
        frame = pd.read_parquet(base / f"{row['split']}.parquet")
        index = frame.index.as_unit("ns")
        assert index.max() < pd.Timestamp("2024-01-01", tz="UTC")
        chosen = np.searchsorted(available, index.asi8, side="left") - 1
        safe = np.maximum(chosen, 0)
        age = (index.asi8 - dates.asi8[safe]) / hour
        expected = np.column_stack([returns[safe], distance[safe], age])
        eligible = (chosen >= 0) & (age >= 0) & (age <= 168) & np.isfinite(expected).all(axis=1)
        expected[~eligible] = np.nan
        np.testing.assert_allclose(
            frame[report["features"]].to_numpy(), expected, rtol=1e-12, atol=1e-14, equal_nan=True
        )
        np.testing.assert_array_equal(frame.eligible_under_assumption, eligible)
        np.testing.assert_array_equal(
            pd.DatetimeIndex(frame.observation_date).as_unit("ns").asi8, dates.asi8[safe]
        )
        np.testing.assert_array_equal(
            pd.DatetimeIndex(frame.assumed_available_at).as_unit("ns").asi8, available[safe]
        )
        paired = pd.read_parquet(base / f"{row['split']}_paired_rows.parquet").index
        pd.testing.assert_index_equal(paired, frame.index[eligible])
        assert row["original_rows"] == len(index) and row["eligible_rows"] == int(eligible.sum())
        assert row["coverage"] == float(eligible.mean())
        verified_rows += len(index)
    for source, digest in report["source_index_sha256"].items():
        path = Path(source)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        fold = path.parent.name if path.name == "train_rows.parquet" else path.parent.parent.name
        split = "train" if path.name == "train_rows.parquet" else "evaluation"
        pd.testing.assert_index_equal(
            pd.read_parquet(path, columns=[]).index,
            pd.read_parquet(folder / "alignment" / fold / f"{split}.parquet", columns=[]).index,
        )
    return {
        "verified": True,
        "verified_rows": verified_rows,
        "independent_searchsorted": True,
        "independent_event_formulas": True,
        "original_indices_preserved": True,
        "historical_availability_proven": False,
        "models_trained": 0,
        "test_evaluated": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    result = verify(args.folder)
    (args.folder / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
