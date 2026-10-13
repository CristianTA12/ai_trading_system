"""Read-only integrity and receipt-time replay verification of a completed pilot."""

import argparse
import hashlib
import json
from pathlib import Path

from src.data.collectors.prospective import closed_asof, parse_kline, summarize


def verify(folder):
    config = json.loads((folder / "session.json").read_text())
    report = json.loads((folder / "report.json").read_text())
    manifest = json.loads((folder / "manifest.json").read_text())
    expected_files = set(manifest["files_sha256"]) | {"manifest.json"}
    assert {p.name for p in folder.iterdir()} == expected_files
    for name, expected in manifest["files_sha256"].items():
        assert Path(name).name == name
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected
    size = sum(p.stat().st_size for p in folder.iterdir())
    assert size <= config["max_bytes"]
    events = [
        json.loads(line)
        for path in sorted(folder.glob("events-*.jsonl"))
        for line in path.read_text().splitlines()
    ]
    assert events[0]["event"] == "session_started"
    assert events[-1]["event"] == "session_stopped"
    assert events[-1]["reason"] == report["stop_reason"]
    assert (
        sum(e["event"] == "connecting" for e in events)
        == report["attempts"]
        <= config["max_attempts"]
    )
    assert sum(e["event"] == "connected" for e in events) == sum(
        e["event"] == "disconnected" for e in events
    )
    records = [
        json.loads(line)
        for path in sorted(folder.glob("messages-*.jsonl"))
        for line in path.read_text().splitlines()
    ]
    previous_mono = -1
    for seq, row in enumerate(records, 1):
        assert row["session"] == config["session"] and row["sequence"] == seq
        assert row["monotonic_ns"] >= previous_mono
        previous_mono = row["monotonic_ns"]
        assert row["provider_timestamp_unit"] == "ms"
    recalculated = summarize(folder, config["started_at_ns"], report["ended_at_ns"])
    assert all(report[key] == value for key, value in recalculated.items())
    # Compare the production forward replay with a reverse scan at receipt
    # boundaries. At exact equality an event must still be unavailable.
    parsed = [(row, parse_kline(row["payload"])) for row in records if row["encoding"] == "text"]
    decisions = {config["started_at_ns"], report["ended_at_ns"]}
    for row, event in parsed:
        if event and event["k"]["x"]:
            decisions.update((row["received_at_ns"], row["received_at_ns"] + 1))
    for decision in sorted(decisions):
        expected = {}
        for row, event in reversed(parsed):
            if row["received_at_ns"] < decision and event and event["k"]["x"]:
                key = event["k"]["t"]
                if key not in expected:
                    expected[key] = {
                        "kline": event["k"],
                        "received_at_ns": row["received_at_ns"],
                        "sequence": row["sequence"],
                    }
        assert closed_asof(records, decision) == expected
    assert report["recording_stopped"] and report["orders_sent"] == report["models_trained"] == 0
    return {
        "verified": True,
        "capture_bytes": size,
        "messages": len(records),
        "receipt_boundaries_checked": len(decisions),
        "stop_reason": report["stop_reason"],
        "clock_synchronization": report["clock_synchronization"],
        "absolute_network_latency_proven": False,
        "capture_manifest_sha256": hashlib.sha256(
            (folder / "manifest.json").read_bytes()
        ).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder), indent=2))


if __name__ == "__main__":
    main()
