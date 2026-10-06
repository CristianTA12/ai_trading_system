"""Bounded SP500 availability audit; persist HTTP errors without exposing the API key."""

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

from scripts.audit_macro_sources import END, START, parse_snapshot
from scripts.audit_vix_api import parse_response

BASE = "https://api.stlouisfed.org/fred/series/"


def request(endpoint, params, key, curl):
    if endpoint not in {"observations", "vintagedates"}:
        raise ValueError("Unsupported endpoint")
    if not re.fullmatch(r"[a-z0-9]{32}", key):
        raise ValueError("FRED_API_KEY missing or invalid format")
    url = BASE + endpoint + "?" + urlencode({**params, "api_key": key})
    try:
        result = subprocess.run(
            [
                curl,
                "--silent",
                "--connect-timeout",
                "8",
                "--max-time",
                "25",
                "--write-out",
                "\n%{http_code}",
                "--config",
                "-",
            ],
            input=f'url = "{url}"\n'.encode(),
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("Transport failure; credential-bearing diagnostics suppressed") from None
    if result.returncode:
        raise RuntimeError(f"Transport failure, curl code {result.returncode}")
    if key.encode() in result.stdout:
        raise RuntimeError("Credential reflected in response; refusing persistence")
    body, status = result.stdout.rsplit(b"\n", 1)
    return body, int(status)


def summarize(body, status, endpoint, day=None):
    payload = json.loads(body)
    if status != 200:
        if not isinstance(payload.get("error_message"), str):
            raise ValueError("Unrecognized HTTP error response")
        return {
            "status": "http_error",
            "error_code": payload.get("error_code"),
            "error_message": payload["error_message"],
        }
    if endpoint == "vintagedates":
        dates = payload["vintage_dates"]
        if (
            payload.get("count") != len(dates)
            or payload.get("offset") != 0
            or dates != sorted(set(dates))
            or any(not START <= x <= END for x in dates)
            or payload.get("realtime_start") != START
            or payload.get("realtime_end") != END
        ):
            raise ValueError("Invalid or incomplete vintage list")
        return {
            "status": "valid_vintage_list",
            "count": len(dates),
            "first": dates[0] if dates else None,
            "last": dates[-1] if dates else None,
        }
    vintage = day or payload["realtime_start"]
    values = parse_response(body, vintage)
    if (values.index > pd.Timestamp(vintage)).any():
        raise ValueError("Future observations in requested vintage")
    latest = (
        parse_snapshot(
            Path("data/external/macro-audit-20261006-retry/SP500.csv").read_bytes(), "SP500"
        )
        .set_index("observation_date")
        .value
    )
    comparable = pd.concat([values.rename("api"), latest.rename("snapshot")], axis=1).dropna()
    return {
        "status": "valid_observations",
        "rows": len(values),
        "nonmissing": int(values.notna().sum()),
        "last_nonmissing": str(values.dropna().index[-1].date()),
        "comparable_with_current_snapshot": len(comparable),
        "changed_values": int(comparable.api.ne(comparable.snapshot).sum()),
        "requested_vintage": day,
        "response_vintage": vintage,
    }


def audit(folder, curl):
    key = os.environ.get("FRED_API_KEY") or dotenv_values(".env").get("FRED_API_KEY") or ""
    if not re.fullmatch(r"[a-z0-9]{32}", key):
        raise ValueError("FRED_API_KEY missing or invalid format")
    folder.mkdir(parents=True, exist_ok=False)
    base = {"series_id": "SP500", "file_type": "json", "offset": 0, "sort_order": "asc"}
    obs = {
        **base,
        "observation_start": START,
        "observation_end": END,
        "units": "lin",
        "output_type": 1,
        "limit": 100000,
    }
    cases = [
        (
            "vintages",
            "vintagedates",
            {**base, "realtime_start": START, "realtime_end": END, "limit": 10000},
            None,
        )
    ]
    for day in ["2019-12-31", "2021-12-31", "2023-01-13", "2023-12-31"]:
        cases.append(
            (day, "observations", {**obs, "realtime_start": day, "realtime_end": day}, day)
        )
    cases.append(("current-bounded", "observations", obs, None))
    records = []
    for name, endpoint, params, day in cases:
        body, status = request(endpoint, params, key, curl)
        (folder / f"{name}.json").write_bytes(body)
        row = {
            "case": name,
            "endpoint": BASE + endpoint,
            "params": params,
            "http_status": status,
            "sha256": hashlib.sha256(body).hexdigest(),
            "retrieved_at": datetime.now(UTC).isoformat(),
            **summarize(body, status, endpoint, day),
        }
        records.append(row)
        (folder / "requests.json").write_text(json.dumps(records, indent=2) + "\n")
        print(
            json.dumps({k: v for k, v in row.items() if k not in {"params", "sha256", "endpoint"}}),
            flush=True,
        )
    report = {
        "requests": len(records),
        "http_errors": sum(r["http_status"] != 200 for r in records),
        "historical_observation_requests_successful": sum(
            r["status"] == "valid_observations" and r.get("requested_vintage") is not None
            for r in records
        ),
        "ready_for_training": False,
        "historical_availability_proven": False,
        "models_trained": 0,
        "test_evaluated": False,
    }
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--curl-executable", default="curl")
    args = parser.parse_args()
    print(json.dumps(audit(args.folder, args.curl_executable), indent=2))
