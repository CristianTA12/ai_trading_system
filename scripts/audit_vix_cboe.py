"""Compare bounded current Cboe history with FRED; never infer point-in-time availability."""

import argparse
import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.audit_macro_sources import END, START, fetch_csv, parse_snapshot

URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
MACRO = Path("data/external/macro-audit-20261006-retry")
VINTAGES = Path("data/external/vix-daily-vintages-20261006")


def bounded_csv(raw):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames != ["DATE", "OPEN", "HIGH", "LOW", "CLOSE"]:
        raise ValueError("Unexpected Cboe schema")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
    writer.writeheader()
    for row in reader:
        day = datetime.strptime(row["DATE"], "%m/%d/%Y").strftime("%Y-%m-%d")
        # Do not interpret or persist values outside the research window.
        if START <= day <= END:
            writer.writerow(row)
    return output.getvalue().encode()


def parse_cboe(raw):
    frame = pd.read_csv(io.BytesIO(raw))
    if frame.columns.tolist() != ["DATE", "OPEN", "HIGH", "LOW", "CLOSE"]:
        raise ValueError("Unexpected Cboe schema")
    dates = pd.to_datetime(frame.pop("DATE"), format="%m/%d/%Y", errors="raise")
    if (
        frame.empty
        or dates.isna().any()
        or dates.duplicated().any()
        or not dates.is_monotonic_increasing
        or not dates.between(START, END).all()
    ):
        raise ValueError("Invalid or out-of-window Cboe dates")
    frame = frame.apply(pd.to_numeric, errors="raise")
    if not np.isfinite(frame.to_numpy()).all() or frame.le(0).any().any():
        raise ValueError("Invalid OHLC values")
    if not (
        frame.LOW.le(frame[["OPEN", "CLOSE"]].min(axis=1))
        & frame.HIGH.ge(frame[["OPEN", "CLOSE"]].max(axis=1))
    ).all():
        raise ValueError("Invalid OHLC range")
    frame.index = pd.DatetimeIndex(dates, name="observation_date")
    return frame


def audit(folder, fetch=False, curl="curl"):
    if fetch:
        folder.mkdir(parents=True, exist_ok=False)
        raw = fetch_csv(URL, "curl", curl)
        bounded = bounded_csv(raw)
        (folder / "cboe-bounded.csv").write_bytes(bounded)
        metadata = {
            "url": URL,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "download_sha256": hashlib.sha256(raw).hexdigest(),
            "bounded_sha256": hashlib.sha256(bounded).hexdigest(),
            "filter": [START, END],
            "full_response_persisted": False,
            "out_of_window_values_analyzed": False,
        }
        (folder / "download.json").write_text(json.dumps(metadata, indent=2) + "\n")
    raw_path = folder / "cboe-bounded.csv"
    metadata = json.loads((folder / "download.json").read_text())
    if hashlib.sha256(raw_path.read_bytes()).hexdigest() != metadata["bounded_sha256"]:
        raise ValueError("Cboe snapshot hash mismatch")
    cboe = parse_cboe(raw_path.read_bytes())
    fred_path = MACRO / "VIXCLS.csv"
    fred = parse_snapshot(fred_path.read_bytes(), "VIXCLS").set_index("observation_date").value
    pair = pd.concat([cboe.CLOSE.rename("cboe"), fred.rename("fred")], axis=1, sort=True)
    equal = pair.cboe.eq(pair.fred) | (pair.cboe.isna() & pair.fred.isna())
    pair["same_value"] = equal
    pair.to_csv(folder / "all-observations.csv")
    quarantine_path = VINTAGES / "quarantine.json"
    quarantine = json.loads(quarantine_path.read_text())
    anomaly_dates = sorted({date for r in quarantine for date in r["future_observation_dates"]})
    anomalies = []
    for day in anomaly_dates:
        date = pd.Timestamp(day)
        before = cboe.loc[cboe.index < date, "CLOSE"]
        row = {
            "date": day,
            "fred": float(fred.loc[date]),
            "cboe": float(cboe.loc[date, "CLOSE"]) if date in cboe.index else None,
            "previous_cboe_close": float(before.iloc[-1]),
            "affected_vintages": sum(day in r["future_observation_dates"] for r in quarantine),
        }
        anomalies.append(row)
    (folder / "anomalies.json").write_text(json.dumps(anomalies, indent=2) + "\n")
    report = {
        "cboe_rows": len(cboe),
        "fred_nonmissing": int(fred.notna().sum()),
        "shared_nonmissing": int(pair.notna().loc[:, ["cboe", "fred"]].all(axis=1).sum()),
        "differing_values_or_missing": int((~equal).sum()),
        "anomaly_dates": len(anomalies),
        "anomaly_dates_matching_cboe": sum(r["cboe"] == r["fred"] for r in anomalies),
        "anomaly_dates_different_from_previous_close": sum(
            r["cboe"] is not None and r["cboe"] != r["previous_cboe_close"] for r in anomalies
        ),
        "cboe_2021_04_16": float(cboe.loc["2021-04-16", "CLOSE"]),
        "historical_availability_proven": False,
        "ready_for_training": False,
        "models_trained": 0,
        "test_evaluated": False,
        "input_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [raw_path, fred_path, quarantine_path]
        },
    }
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--curl-executable", default="curl")
    args = parser.parse_args()
    print(json.dumps(audit(args.folder, args.fetch, args.curl_executable), indent=2))
