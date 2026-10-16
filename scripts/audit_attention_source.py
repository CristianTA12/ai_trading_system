"""One bounded Wikimedia development-sample request; no prices or backtests."""

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia.org/all-access/user/Bitcoin/daily/2020010100/2020013100"
USER_AGENT = "ai-trading-system-source-audit/1.0 (https://github.com/CristianTA12/ai_trading_system) Python-urllib"


def inspect(payload):
    expected = {(date(2020, 1, 1) + timedelta(days=i)).strftime("%Y%m%d00") for i in range(31)}
    items = payload["items"]
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    seen = set()
    for row in items:
        for key, value in {
            "project": "en.wikipedia",
            "article": "Bitcoin",
            "access": "all-access",
            "agent": "user",
            "granularity": "daily",
        }.items():
            if row.get(key) != value:
                raise ValueError(f"Unexpected {key}")
        stamp = row.get("timestamp")
        if stamp not in expected or stamp in seen:
            raise ValueError("Unexpected or duplicate observation date")
        if (
            isinstance(row.get("views"), bool)
            or not isinstance(row.get("views"), int)
            or row["views"] < 0
        ):
            raise ValueError("views must be a nonnegative integer")
        seen.add(stamp)
    return {
        "expected_days": 31,
        "observed_days": len(seen),
        "missing_days": sorted(expected - seen),
        "coverage_fraction": len(seen) / 31,
        "returned_fields": sorted({key for row in items for key in row}),
        "missing_values_filled": False,
        "historical_publication_time_proven": False,
        "historical_revision_history_proven": False,
        "causal_backtest_ready": False,
    }


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    request = urllib.request.Request(
        URL, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    metadata = {
        "url": URL,
        "user_agent": USER_AGENT,
        "requested_at_ns": time.time_ns(),
        "max_requests": 1,
        "timeout_seconds": 20,
        "body_limit_bytes": 1_000_000,
    }
    try:
        try:
            response = urllib.request.urlopen(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read(1_000_001)
            metadata.update(
                status=response.status,
                received_at_ns=time.time_ns(),
                response_headers={
                    k: v
                    for k, v in response.headers.items()
                    if k.lower()
                    in {"date", "last-modified", "etag", "cache-control", "content-type"}
                },
            )
        if len(body) > 1_000_000:
            raise ValueError("Response exceeds bounded audit size")
        (output / "response.bin").write_bytes(body)
        if metadata["status"] == 200:
            report = {"access": "ok", **inspect(json.loads(body))}
        else:
            report = {
                "access": "http_error",
                "status": metadata["status"],
                "causal_backtest_ready": False,
                "missing_values_filled": False,
            }
    except (OSError, ValueError, KeyError, TypeError) as error:
        report = {
            "access": "failed",
            "error_type": type(error).__name__,
            "causal_backtest_ready": False,
        }
    (output / "request.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    manifest = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
