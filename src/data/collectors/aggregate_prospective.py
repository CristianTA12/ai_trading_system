"""UTC-aligned complete bars reconstructed from recorded receipt-time knowledge."""

import argparse
import json
from decimal import Decimal, localcontext
from pathlib import Path

from src.data.collectors.prospective import MINUTE_MS, closed_asof


def _combine(parts, start, minutes):
    klines = [p["kline"] for p in parts]
    # Decimal strings avoid binary float rounding in derived market quantities.
    with localcontext() as context:
        context.prec = 80
        kline = {
            "t": start,
            "T": start + minutes * MINUTE_MS - 1,
            "s": "BTCUSDT",
            "i": "15m" if minutes == 15 else "1h",
            "x": True,
            "o": klines[0]["o"],
            "c": klines[-1]["c"],
            "h": str(max(Decimal(k["h"]) for k in klines)),
            "l": str(min(Decimal(k["l"]) for k in klines)),
            "n": sum(k["n"] for k in klines),
        }
        for field in ("v", "q", "V", "Q"):
            kline[field] = str(sum((Decimal(k[field]) for k in klines), Decimal(0)))
    sources = []
    for part in parts:
        sources.extend(
            part.get("sources")
            or [
                {
                    "open_time_ms": part["kline"]["t"],
                    "sequence": part["sequence"],
                    "received_at_ns": part["received_at_ns"],
                }
            ]
        )
    return {
        "kline": kline,
        "available_at_ns": max(source["received_at_ns"] for source in sources),
        "sources": sources,
    }


def _complete_groups(bars, input_minutes, output_minutes):
    width = output_minutes * MINUTE_MS
    result = {}
    for start in sorted({t // width * width for t in bars}):
        expected = range(start, start + width, input_minutes * MINUTE_MS)
        if all(t in bars for t in expected):
            result[start] = _combine([bars[t] for t in expected], start, output_minutes)
    return result


def aggregate_asof(records, decision_ns):
    """One session in receipt order; only versions received strictly before decision.

    Missing minutes suppress the entire bar. Hour bars require four complete
    UTC quarter-hours. No forward fill, historical backfill or clock correction.
    Provenance sequences refer to the supplied session's original raw records.
    """
    minutes = closed_asof(records, decision_ns)
    quarters = _complete_groups(minutes, 1, 15)
    return {"15m": quarters, "1h": _complete_groups(quarters, 15, 60)}


def main():
    """Read a verified closed session and print a derived snapshot; never alter raw."""
    from src.data.collectors.verify_prospective import verify

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--decision-ns", type=int)
    args = parser.parse_args()
    verification = verify(args.folder)
    report = json.loads((args.folder / "report.json").read_text())
    config = json.loads((args.folder / "session.json").read_text())
    decision = args.decision_ns if args.decision_ns is not None else report["ended_at_ns"]
    if not config["started_at_ns"] <= decision <= report["ended_at_ns"]:
        parser.error("decision must lie within the recorded session")
    records = [
        json.loads(line)
        for path in sorted(args.folder.glob("messages-*.jsonl"))
        for line in path.read_text().splitlines()
    ]
    print(
        json.dumps(
            {
                "session": config["session"],
                "capture_manifest_sha256": verification["capture_manifest_sha256"],
                "decision_ns": decision,
                "clock_synchronization": report["clock_synchronization"],
                "bars": aggregate_asof(records, decision),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
