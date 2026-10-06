"""Bounded macro snapshot audit. Does not establish historical publication times.

Fetch latest-vintage 2019-11--2023-12 observations only, or audit existing raw
files offline. No feature generation, BTC dataset reads, training or backtests.
"""

import argparse
import hashlib
import io
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

SERIES = ("SP500", "VIXCLS", "DTWEXBGS")
START, END = "2019-11-01", "2023-12-31"


def parse_snapshot(raw, series):
    if series not in SERIES:
        raise ValueError("Unknown series")
    frame = pd.read_csv(io.BytesIO(raw), na_values=["."], keep_default_na=True)
    if list(frame.columns) not in (["observation_date", series], ["DATE", series]):
        raise ValueError("Unexpected source schema")
    frame.columns = ["observation_date", "value"]
    frame["observation_date"] = pd.to_datetime(
        frame.observation_date, format="%Y-%m-%d", errors="raise"
    )
    if frame.empty or frame.observation_date.isna().any():
        raise ValueError("Empty or invalid dates")
    if (
        frame.observation_date.duplicated().any()
        or not frame.observation_date.is_monotonic_increasing
    ):
        raise ValueError("Duplicate or unsorted dates")
    if not frame.observation_date.between(START, END).all():
        raise ValueError("Response exceeds audit window; do not use validation/test observations")
    frame["value"] = pd.to_numeric(frame.value, errors="raise")
    valid = frame.value.dropna()
    if valid.empty or not np.isfinite(valid).all() or valid.le(0).any():
        raise ValueError("Missing/nonpositive/nonfinite series")
    return frame


def summarize(frame):
    valid = frame.loc[frame.value.notna(), "observation_date"]
    weekdays = pd.date_range(START, END, freq="B")
    # These dates include legitimate holidays. Do not mislabel all as data gaps.
    missing = weekdays.difference(pd.DatetimeIndex(valid))
    folds = {}
    for year in (2022, 2023):
        for half, start, end in (
            ("H1", f"{year}-01-01", f"{year}-06-30"),
            ("H2", f"{year}-07-01", f"{year}-12-31"),
        ):
            dates = valid.loc[valid.between(start, end)]
            folds[f"{year} {half}"] = {"observations": len(dates)}
    return {
        "rows": len(frame),
        "nonmissing": len(valid),
        "null_rows": int(frame.value.isna().sum()),
        "first_date": str(valid.min().date()),
        "last_date": str(valid.max().date()),
        "duplicates": 0,
        "max_calendar_gap_days": float(valid.diff().dt.days.max()),
        "weekdays_without_value_unclassified": [str(x.date()) for x in missing],
        "fold_counts": folds,
        "causal_15m_coverage": None,
        "historical_available_at_verified": False,
        "point_in_time_vintages_verified": False,
    }


def audit(folder, fetch=False):
    if fetch:
        folder.mkdir(parents=True, exist_ok=False)
    elif not folder.is_dir():
        raise ValueError("Offline audit requires existing raw directory")
    attempts = []
    if fetch:
        for series in SERIES:
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={START}&coed={END}"
            record = {"series": series, "url": url, "attempted_at": datetime.now(UTC).isoformat()}
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "ai-trading-system source audit"}
                )
                with urllib.request.urlopen(req, timeout=20) as response:
                    raw = response.read()
                (folder / f"{series}.csv").write_bytes(raw)
                record.update(
                    status="downloaded", sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)
                )
            except Exception as error:
                record.update(status="failed", error=f"{type(error).__name__}: {error}")
            attempts.append(record)
            (folder / "download.json").write_text(json.dumps(attempts, indent=2) + "\n")
            print(f"{series}: {record['status']}", flush=True)
    results = {}
    for series in SERIES:
        path = folder / f"{series}.csv"
        if not path.exists():
            results[series] = {"status": "raw_unavailable", "causal_15m_coverage": None}
            continue
        raw = path.read_bytes()
        try:
            results[series] = {
                "status": "snapshot_valid_only",
                "sha256": hashlib.sha256(raw).hexdigest(),
                **summarize(parse_snapshot(raw, series)),
            }
        except (ValueError, TypeError, pd.errors.ParserError, UnicodeDecodeError) as error:
            results[series] = {
                "status": "invalid_snapshot",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "error": str(error),
            }
    result = {
        "window": [START, END],
        "series": results,
        "ready_for_experiment": False,
        "reason": "Snapshot availability alone does not prove historical publication or vintages",
        "models_trained": 0,
        "backtests_run": 0,
        "test_evaluated": False,
    }
    (folder / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Download into a NEW directory; otherwise audit offline",
    )
    args = parser.parse_args()
    audit(args.folder, args.fetch)
