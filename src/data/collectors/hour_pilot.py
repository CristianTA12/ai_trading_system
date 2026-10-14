"""One bounded live session spanning a full UTC hour, with automatic offline review."""

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

from src.data.collectors.aggregate_prospective import aggregate_asof
from src.data.collectors.prospective import capture, encoded
from src.data.collectors.verify_prospective import verify

HOUR_NS = 3_600_000_000_000


def plan(now_ns):
    # Always start the target at the next whole hour, even at exact equality:
    # socket setup may otherwise miss the start of the intended window.
    target_start = (now_ns // HOUR_NS + 1) * HOUR_NS
    target_end = target_start + HOUR_NS
    return {
        "planned_at_ns": now_ns,
        "target_start_ms": target_start // 1_000_000,
        "target_end_exclusive_ms": target_end // 1_000_000,
        "planned_stop_ns": target_end + 30_000_000_000,
        "seconds": (target_end + 30_000_000_000 - now_ns) / 1e9,
        "max_bytes": 50_000_000,
        "max_attempts": 3,
    }


def assess(bars, report, recipe):
    target = bars["1h"].get(recipe["target_start_ms"])
    complete = target is not None
    return {
        "target_hour_complete": complete,
        "quarter_hours": len(bars["15m"]),
        "hours": len(bars["1h"]),
        "quality_pass": (
            complete
            and report["stop_reason"] == "duration_limit"
            and report["invalid_messages"] == 0
            and report["wall_clock_jumps_over_1s"] == 0
        ),
        "clock_synchronization": report["clock_synchronization"],
        "absolute_network_latency_proven": False,
        "models_trained": 0,
        "orders_sent": 0,
    }


async def run(folder):
    folder.mkdir(parents=True, exist_ok=False)
    recipe = plan(time.time_ns())
    recipe["source_sha256"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            Path(__file__),
            Path(__file__).with_name("aggregate_prospective.py"),
            Path(__file__).with_name("verify_prospective.py"),
        )
    }
    (folder / "plan.json").write_bytes(encoded(recipe))
    print(json.dumps({"state": "starting", **recipe}), flush=True)
    try:
        await capture(folder / "capture", recipe["seconds"], recipe["max_bytes"])
        verification = verify(folder / "capture")
        report = json.loads((folder / "capture/report.json").read_text())
        records = [
            json.loads(line)
            for path in sorted((folder / "capture").glob("messages-*.jsonl"))
            for line in path.read_text().splitlines()
        ]
        bars = aggregate_asof(records, report["ended_at_ns"])
        (folder / "aggregates.json").write_bytes(
            encoded(
                {
                    "decision_ns": report["ended_at_ns"],
                    "capture_manifest_sha256": verification["capture_manifest_sha256"],
                    "bars": bars,
                }
            )
        )
        verdict = assess(bars, report, recipe)
        (folder / "verification.json").write_bytes(encoded(verification))
        (folder / "result.json").write_bytes(encoded({"state": "finished", **verdict}))
        manifest = {
            str(p.relative_to(folder)).replace("\\", "/"): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in sorted(folder.rglob("*"))
            if p.is_file()
        }
        (folder / "review_manifest.json").write_bytes(encoded({"files_sha256": manifest}))
        print(json.dumps(verdict), flush=True)
        return 0 if verdict["quality_pass"] else 2
    except Exception as exc:
        (folder / "failure.json").write_bytes(
            encoded({"state": "failed", "type": type(exc).__name__})
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.output)))


if __name__ == "__main__":
    main()
