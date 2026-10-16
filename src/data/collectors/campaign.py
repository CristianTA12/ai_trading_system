"""Bounded five-hour campaign; separate immutable captures, no gap filling."""

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

from src.data.collectors.aggregate_prospective import aggregate_asof
from src.data.collectors.prospective import capture, encoded
from src.data.collectors.verify_prospective import verify


async def run(folder):
    folder.mkdir(parents=True, exist_ok=False)
    started = time.time_ns()
    deadline = time.monotonic() + 18000
    marker = folder / "STOP"
    plan = {
        "started_at_ns": started,
        "planned_stop_ns": started + 18000 * 1_000_000_000,
        "duration_seconds": 18000,
        "maximum_sessions": 3,
        "max_capture_bytes_per_session": 50_000_000,
        "max_total_raw_capture_bytes": 150_000_000,
        "stop_file": str(marker.resolve()),
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                Path(__file__),
                Path(__file__).with_name("prospective.py"),
                Path(__file__).with_name("aggregate_prospective.py"),
                Path(__file__).with_name("verify_prospective.py"),
            )
        },
    }
    (folder / "plan.json").write_bytes(encoded(plan))
    print(json.dumps(plan), flush=True)
    summaries = []
    reason = "duration_limit"
    try:
        for index in range(1, 4):
            remaining = deadline - time.monotonic()
            if marker.exists():
                reason = "user_stop"
                break
            if remaining <= 0:
                break
            session = folder / f"session-{index:02d}"
            await capture(session, seconds=min(7200, remaining), stop_file=marker)
            verification = verify(session)
            report = json.loads((session / "report.json").read_text())
            records = [
                json.loads(line)
                for p in sorted(session.glob("messages-*.jsonl"))
                for line in p.read_text().splitlines()
            ]
            bars = aggregate_asof(records, report["ended_at_ns"])
            review = folder / f"review-{index:02d}.json"
            review.write_bytes(
                encoded(
                    {
                        "verification": verification,
                        "bars": bars,
                        "decision_ns": report["ended_at_ns"],
                    }
                )
            )
            summaries.append(
                {
                    "session": session.name,
                    "messages": report["messages"],
                    "stop_reason": report["stop_reason"],
                    "missing_closed_minutes": report["missing_closed_minutes"],
                    "quarter_hours": len(bars["15m"]),
                    "hours": len(bars["1h"]),
                }
            )
            (folder / "progress.json").write_bytes(encoded({"completed_sessions": summaries}))
            if report["stop_reason"] != "duration_limit" or report["messages"] == 0:
                reason = report["stop_reason"] if report["messages"] else "no_messages"
                break
        result = {
            "state": "finished",
            "stop_reason": reason,
            "sessions": summaries,
            "ended_at_ns": time.time_ns(),
            "models_trained": 0,
            "orders_sent": 0,
            "continuous_coverage_claimed": False,
        }
        (folder / "result.json").write_bytes(encoded(result))
        print(json.dumps(result), flush=True)
        return 0 if reason in {"duration_limit", "user_stop"} else 2
    except Exception as exc:
        (folder / "failure.json").write_bytes(
            encoded(
                {"state": "failed", "type": type(exc).__name__, "completed_sessions": summaries}
            )
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.output)))


if __name__ == "__main__":
    main()
