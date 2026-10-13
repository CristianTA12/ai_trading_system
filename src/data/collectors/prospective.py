"""Bounded public kline recorder. No credentials, strategies or historical reads."""

import argparse
import asyncio
import base64
import hashlib
import json
import platform
import subprocess
import time
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

import websockets
from websockets.asyncio.client import connect

URL = "wss://data-stream.binance.vision/ws/btcusdt@kline_1m"
VERSION = "1"
MINUTE_MS = 60_000


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, allow_nan=False) + "\n").encode()


def parse_kline(raw):
    """Explicit millisecond schema; malformed payloads remain in the raw log."""
    try:
        value = json.loads(raw)
        k = value["k"]
        if (
            value["e"] != "kline"
            or value["s"] != "BTCUSDT"
            or k["s"] != "BTCUSDT"
            or k["i"] != "1m"
        ):
            return None
        if not isinstance(k["x"], bool):
            return None
        for field in (value["E"], k["t"], k["T"]):
            if (
                not isinstance(field, int)
                or isinstance(field, bool)
                or not 1_000_000_000_000 <= field < 10_000_000_000_000
            ):
                return None
        if k["t"] % MINUTE_MS or k["T"] != k["t"] + MINUTE_MS - 1:
            return None
        quantities = {
            name: Decimal(str(k[name])) for name in ("o", "h", "l", "c", "v", "q", "V", "Q")
        }
        if any(not v.is_finite() or v < 0 for v in quantities.values()):
            return None
        if any(quantities[n] <= 0 for n in ("o", "h", "l", "c")):
            return None
        if (
            not quantities["l"]
            <= min(quantities["o"], quantities["c"])
            <= max(quantities["o"], quantities["c"])
            <= quantities["h"]
        ):
            return None
        if quantities["V"] > quantities["v"] or quantities["Q"] > quantities["q"]:
            return None
        if not isinstance(k["n"], int) or isinstance(k["n"], bool) or k["n"] < 0:
            return None
        return value
    except (ValueError, TypeError, KeyError, InvalidOperation, UnicodeError):
        return None


def closed_asof(records, decision_ns):
    """Latest received closed revision per minute, strictly before a local decision."""
    closed = {}
    for row in records:
        if row["received_at_ns"] >= decision_ns or row["encoding"] != "text":
            continue
        event = parse_kline(row["payload"])
        if event and event["k"]["x"]:
            closed[event["k"]["t"]] = {
                "kline": event["k"],
                "received_at_ns": row["received_at_ns"],
                "sequence": row["sequence"],
            }
    return closed


class Journal:
    """Append-only JSONL with bounded bytes and rotation; never truncate existing files."""

    def __init__(self, folder, prefix, budget, rotation=4_000_000):
        self.folder, self.prefix, self.budget = folder, prefix, budget
        self.rotation = rotation
        self.total, self.part, self.current = 0, 0, 0
        self.stream = None

    def append(self, record):
        blob = encoded(record)
        if self.total + len(blob) > self.budget:
            return False
        if self.stream is None or self.current + len(blob) > self.rotation:
            self.close()
            self.stream = (self.folder / f"{self.prefix}-{self.part:04d}.jsonl").open("xb")
            self.part += 1
            self.current = 0
        self.stream.write(blob)
        self.stream.flush()
        self.total += len(blob)
        self.current += len(blob)
        return True

    def close(self):
        if self.stream:
            self.stream.close()
            self.stream = None


def summarize(folder, started_ns, ended_ns):
    seen, final_signatures, records = set(), {}, []
    invalid = duplicates = revisions = clock_jumps = 0
    previous = None
    delays, close_delays = [], []
    for path in sorted(folder.glob("messages-*.jsonl")):
        with path.open() as stream:
            for line in stream:
                row = json.loads(line)
                assert row["sequence"] == len(records) + 1
                records.append(row)
                if previous:
                    delta = (row["received_at_ns"] - previous["received_at_ns"]) - (
                        row["monotonic_ns"] - previous["monotonic_ns"]
                    )
                    clock_jumps += abs(delta) > 1_000_000_000
                previous = row
                digest = hashlib.sha256(row["payload"].encode()).hexdigest()
                duplicates += digest in seen
                seen.add(digest)
                event = parse_kline(row["payload"]) if row["encoding"] == "text" else None
                if event is None:
                    invalid += 1
                    continue
                delays.append(row["received_at_ns"] / 1e6 - event["E"])
                k = event["k"]
                if k["x"]:
                    signature = json.dumps(k, sort_keys=True)
                    revisions += (
                        k["t"] in final_signatures and final_signatures[k["t"]] != signature
                    )
                    final_signatures[k["t"]] = signature
                    close_delays.append(row["received_at_ns"] / 1e6 - (k["T"] + 1))
    final = closed_asof(records, ended_ns)
    first_full = ((started_ns // 1_000_000 + MINUTE_MS - 1) // MINUTE_MS) * MINUTE_MS
    end_ms = ended_ns // 1_000_000
    expected = list(range(first_full, (end_ms // MINUTE_MS) * MINUTE_MS, MINUTE_MS))
    missing = [t for t in expected if t not in final]
    return {
        "messages": len(records),
        "invalid_messages": invalid,
        "duplicate_payloads": duplicates,
        "closed_revisions": revisions,
        "unique_closed_minutes": len(final),
        "fully_observed_session_minutes_expected": len(expected),
        "missing_closed_minutes": missing,
        "wall_clock_jumps_over_1s": clock_jumps,
        "clock_synchronization": "unknown",
        "event_to_receive_ms_min": min(delays) if delays else None,
        "event_to_receive_ms_max": max(delays) if delays else None,
        "close_to_receive_ms_max": max(close_delays) if close_delays else None,
        "closed_arrivals_over_15min": sum(d > 900_000 for d in close_delays),
        "absolute_network_latency_proven": False,
    }


async def capture(folder, seconds=600, max_bytes=50_000_000, max_attempts=3, connector=connect):
    if (
        not 0 < seconds <= 600
        or not 1_000_000 <= max_bytes <= 50_000_000
        or not 1 <= max_attempts <= 3
    ):
        raise ValueError("Pilot limits: <=600 seconds, 1–50 MB, 1–3 attempts")
    folder.mkdir(parents=True, exist_ok=False)
    session = str(uuid.uuid4())
    started_ns, started_mono = time.time_ns(), time.monotonic_ns()
    deadline = asyncio.get_running_loop().time() + seconds
    messages = Journal(folder, "messages", max_bytes - 65_536)
    events = Journal(folder, "events", 32_768)
    sequence = attempts = 0
    reason = "duration_limit"

    def log(kind, **detail):
        events.append(
            {
                "event": kind,
                "received_at_ns": time.time_ns(),
                "monotonic_ns": time.monotonic_ns(),
                "session": session,
                **detail,
            }
        )

    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL, timeout=5
        ).strip()
    except (OSError, subprocess.SubprocessError):
        revision = "unknown"
    config = {
        "session": session,
        "version": VERSION,
        "git_revision": revision,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "endpoint": URL,
        "provider_timestamp_unit": "ms",
        "duration_seconds": seconds,
        "max_bytes": max_bytes,
        "max_attempts": max_attempts,
        "started_at_ns": started_ns,
        "python": platform.python_version(),
        "websockets": websockets.__version__,
        "clock_synchronization": "unknown",
        "purpose": "data_quality_not_strategy_test",
    }
    if platform.system() == "Windows":
        try:
            clock = subprocess.run(["w32tm", "/query", "/status"], capture_output=True, timeout=5)
            config["clock_probe"] = {
                "command": "w32tm /query /status",
                "returncode": clock.returncode,
                "stdout_base64": base64.b64encode(clock.stdout).decode(),
                "stderr_base64": base64.b64encode(clock.stderr).decode(),
                "interpretation": "raw evidence; synchronization not automatically established",
            }
        except (OSError, subprocess.SubprocessError):
            config["clock_probe"] = {"status": "unavailable"}
    (folder / "session.json").write_bytes(encoded(config))
    log("session_started")
    try:
        while asyncio.get_running_loop().time() < deadline and attempts < max_attempts:
            attempts += 1
            log("connecting", attempt=attempts)
            try:
                async with asyncio.timeout_at(deadline):
                    async with connector(
                        URL,
                        open_timeout=15,
                        close_timeout=3,
                        ping_interval=None,
                        max_size=262_144,
                        max_queue=4,
                        compression=None,
                    ) as ws:
                        log("connected", attempt=attempts)
                        try:
                            while True:
                                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                                received_ns, monotonic_ns = time.time_ns(), time.monotonic_ns()
                                record = {
                                    "session": session,
                                    "sequence": sequence + 1,
                                    "received_at_ns": received_ns,
                                    "monotonic_ns": monotonic_ns,
                                    "provider_timestamp_unit": "ms",
                                    "encoding": "text" if isinstance(raw, str) else "base64",
                                    "payload": raw
                                    if isinstance(raw, str)
                                    else base64.b64encode(raw).decode(),
                                }
                                if not messages.append(record):
                                    reason = "byte_limit"
                                    log(
                                        "message_not_persisted_byte_limit",
                                        next_sequence=sequence + 1,
                                    )
                                    return
                                sequence += 1
                        finally:
                            log("disconnected", attempt=attempts)
            except TimeoutError:
                if asyncio.get_running_loop().time() >= deadline:
                    reason = "duration_limit"
                    break
                log("connection_or_receive_timeout", attempt=attempts)
            except (OSError, websockets.exceptions.WebSocketException) as exc:
                log("connection_error", attempt=attempts, exception_type=type(exc).__name__)
            if attempts < max_attempts:
                await asyncio.sleep(
                    min(2**attempts, max(0, deadline - asyncio.get_running_loop().time()))
                )
        if attempts >= max_attempts and asyncio.get_running_loop().time() < deadline:
            reason = "attempt_limit"
    except asyncio.CancelledError:
        reason = "cancelled"
    except Exception:
        reason = "unexpected_error"
        raise
    finally:
        ended_ns = time.time_ns()
        log("session_stopped", reason=reason, messages=sequence)
        messages.close()
        events.close()
        report = summarize(folder, started_ns, ended_ns)
        report.update(
            stop_reason=reason,
            attempts=attempts,
            ended_at_ns=ended_ns,
            elapsed_seconds=(time.monotonic_ns() - started_mono) / 1e9,
            recording_stopped=True,
            models_trained=0,
            orders_sent=0,
        )
        (folder / "report.json").write_bytes(encoded(report))
        manifest = {
            "files_sha256": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(folder.iterdir())
                if p.is_file()
            }
        }
        (folder / "manifest.json").write_bytes(encoded(manifest))
        assert sum(p.stat().st_size for p in folder.iterdir() if p.is_file()) <= max_bytes
        print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=600)
    parser.add_argument("--max-bytes", type=int, default=50_000_000)
    args = parser.parse_args()
    asyncio.run(capture(args.output, args.seconds, args.max_bytes))
    report = json.loads((args.output / "report.json").read_text())
    if report["messages"] == 0 or report["stop_reason"] in {"attempt_limit", "unexpected_error"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
