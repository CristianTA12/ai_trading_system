"""Contrast archived VIX graph anomalies with authenticated FRED observations.

The key is supplied to curl through stdin, never argv or saved request metadata.
This diagnostic preserves future observations; it does not approve training data.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
from dotenv import dotenv_values

from scripts.audit_macro_sources import END, START

ENDPOINT = "https://api.stlouisfed.org/fred/series/observations"
GRAPH = Path("data/external/vix-daily-vintages-20261006")


def fetch(day, key, curl):
    params = {
        "series_id": "VIXCLS",
        "file_type": "json",
        "realtime_start": day,
        "realtime_end": day,
        "observation_start": START,
        "observation_end": END,
        "units": "lin",
        "output_type": 1,
        "sort_order": "asc",
        "limit": 100000,
        "offset": 0,
    }
    url = ENDPOINT + "?" + urlencode({**params, "api_key": key})
    try:
        response = subprocess.run(
            [
                curl,
                "--silent",
                "--fail",
                "--connect-timeout",
                "8",
                "--max-time",
                "25",
                "--config",
                "-",
            ],
            input=f'url = "{url}"\n'.encode(),
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("FRED transport failed; secret-bearing diagnostics suppressed") from None
    if response.returncode:
        raise RuntimeError(f"FRED request failed (curl code {response.returncode})")
    if key.encode() in response.stdout:
        raise RuntimeError("Response unexpectedly contains credential; refusing persistence")
    return response.stdout, params


def parse_response(raw, day):
    payload = json.loads(raw)
    if payload.get("realtime_start") != day or payload.get("realtime_end") != day:
        raise ValueError("Response realtime window mismatch")
    if payload.get("observation_start") != START or payload.get("observation_end") != END:
        raise ValueError("Response observation window mismatch")
    observations = payload["observations"]
    if payload.get("count") != len(observations) or payload.get("offset") != 0:
        raise ValueError("Incomplete or paginated response")
    frame = pd.DataFrame(observations)
    if frame.empty or not {"date", "value", "realtime_start", "realtime_end"} <= set(frame):
        raise ValueError("Unexpected observation schema")
    if not (frame.realtime_start.eq(day) & frame.realtime_end.eq(day)).all():
        raise ValueError("Observation realtime window mismatch")
    dates = pd.to_datetime(frame.date, format="%Y-%m-%d", errors="raise")
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("Invalid observation order")
    if not dates.between(START, END).all():
        raise ValueError("Observation outside audit window")
    values = pd.to_numeric(frame.value.replace(".", float("nan")), errors="raise")
    valid = values.dropna()
    if valid.empty or not valid.between(0, float("inf"), inclusive="neither").all():
        raise ValueError("Invalid VIX values")
    return pd.Series(values.to_numpy(), index=pd.DatetimeIndex(dates), name="api")


def compare(raw, day, graph):
    api = parse_response(raw, day)
    graph_path = graph / "raw" / f"{day}.csv"
    archived = pd.read_csv(graph_path, index_col=0, parse_dates=True).iloc[:, 0]
    pair = pd.concat([api, archived.rename("graph")], axis=1)
    same = pair.api.eq(pair.graph) | (pair.api.isna() & pair.graph.isna())
    future = api.loc[api.index > pd.Timestamp(day)]
    target = pd.Timestamp("2021-04-16")
    return {
        "vintage_date": day,
        "rows": len(api),
        "future_rows": len(future),
        "future_nonmissing": int(future.notna().sum()),
        "future_observations": {
            str(k.date()): None if pd.isna(v) else float(v) for k, v in future.items()
        },
        "graph_differing_values": int((~same).sum()),
        "same_dates_as_graph": api.index.equals(archived.index),
        "graph_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        "observation_2021_04_16": (
            float(api.loc[target]) if target in api.index and pd.notna(api.loc[target]) else None
        ),
    }


def audit(output, curl):
    key = os.environ.get("FRED_API_KEY") or dotenv_values(".env").get("FRED_API_KEY")
    if not key or not re.fullmatch(r"[a-z0-9]{32}", key):
        raise ValueError("FRED_API_KEY missing or invalid format; credential not displayed")
    output.mkdir(parents=True, exist_ok=False)
    (output / "raw").mkdir()
    quarantined = json.loads((GRAPH / "quarantine.json").read_text())
    days = sorted(
        {r["vintage_date"] for r in quarantined}
        | {
            "2021-04-16",
            "2021-04-19",
            "2021-06-02",
            "2021-06-03",
            "2023-01-12",
            "2023-01-16",
            "2023-01-17",
        }
    )
    # Authenticate and inspect the primary anomaly first.
    days.remove("2023-01-13")
    days.insert(0, "2023-01-13")
    records = []
    for day in days:
        raw, params = fetch(day, key, curl)
        (output / "raw" / f"{day}.json").write_bytes(raw)
        record = compare(raw, day, GRAPH)
        record.update(
            params=params,
            endpoint=ENDPOINT,
            retrieved_at=datetime.now(UTC).isoformat(),
            sha256=hashlib.sha256(raw).hexdigest(),
        )
        records.append(record)
        (output / "comparisons.json").write_text(json.dumps(records, indent=2) + "\n")
        print(
            json.dumps(
                {
                    k: record[k]
                    for k in [
                        "vintage_date",
                        "future_nonmissing",
                        "graph_differing_values",
                        "observation_2021_04_16",
                    ]
                }
            ),
            flush=True,
        )
    report = {
        "api_authenticated": True,
        "vintages_checked": len(records),
        "vintages_with_future_values": sum(r["future_nonmissing"] > 0 for r in records),
        "graph_value_mismatches": sum(r["graph_differing_values"] for r in records),
        "ready_for_training": False,
        "intraday_availability_proven": False,
        "models_trained": 0,
        "test_evaluated": False,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--curl-executable", default="curl")
    args = parser.parse_args()
    print(json.dumps(audit(args.output, args.curl_executable), indent=2))
