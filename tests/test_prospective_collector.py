import asyncio
import hashlib
import json

import pytest

from src.data.collectors.prospective import Journal, capture, closed_asof, parse_kline, summarize
from src.data.collectors.verify_prospective import verify

START = 1609459200000


def payload(closed=True, volume="10"):
    return json.dumps(
        {
            "e": "kline",
            "E": START + 60001,
            "s": "BTCUSDT",
            "k": {
                "t": START,
                "T": START + 59999,
                "s": "BTCUSDT",
                "i": "1m",
                "x": closed,
                "o": "100",
                "h": "101",
                "l": "99",
                "c": "100",
                "v": volume,
                "q": "1000",
                "V": "3",
                "Q": "300",
                "n": 2,
            },
        }
    )


def record(raw, seq, received):
    return {
        "payload": raw,
        "encoding": "text",
        "sequence": seq,
        "received_at_ns": received,
        "monotonic_ns": received,
    }


def test_schema_explicit_units_and_malformed_payload():
    assert parse_kline(payload()) is not None
    assert parse_kline("invalid") is None
    assert parse_kline("[]") is None
    value = json.loads(payload())
    value["E"] *= 1000
    assert parse_kline(json.dumps(value)) is None
    value = json.loads(payload())
    value["k"]["x"] = "true"
    assert parse_kline(json.dumps(value)) is None
    assert parse_kline(payload(volume="NaN")) is None


def test_late_close_and_revision_are_available_only_after_receipt():
    rows = [
        record(payload(False), 1, 10),
        record(payload(), 2, 20),
        record(payload(volume="12"), 3, 40),
    ]
    assert closed_asof(rows, 20) == {}
    assert closed_asof(rows, 30)[START]["kline"]["v"] == "10"
    assert closed_asof(rows, 40)[START]["kline"]["v"] == "10"
    assert closed_asof(rows, 41)[START]["kline"]["v"] == "12"


def test_rotation_limit_and_no_overwrite(tmp_path):
    journal = Journal(tmp_path, "messages", 100, rotation=20)
    assert journal.append({"a": "12345678"})
    assert journal.append({"a": "12345678"})
    assert not journal.append({"large": "x" * 100})
    journal.close()
    assert len(list(tmp_path.glob("messages-*.jsonl"))) == 2
    with pytest.raises(FileExistsError):
        Journal(tmp_path, "messages", 100).append({"a": 1})


def test_report_duplicates_revisions_missing_minutes_and_clock_jump(tmp_path):
    journal = Journal(tmp_path, "messages", 10000)
    base = (START + 60002) * 1_000_000
    rows = [
        record(payload(), 1, base),
        record(payload(), 2, base + 1),
        record(payload(volume="12"), 3, base + 2),
        record("bad", 4, base + 3),
    ]
    rows[-1]["monotonic_ns"] -= 2_000_000_000
    for row in rows:
        journal.append(row)
    journal.close()
    result = summarize(tmp_path, START * 1_000_000, (START + 180001) * 1_000_000)
    assert result["duplicate_payloads"] == 1
    assert result["closed_revisions"] == 1
    assert result["invalid_messages"] == 1
    assert result["wall_clock_jumps_over_1s"] == 1
    assert result["missing_closed_minutes"] == [START + 60000, START + 120000]


class FakeConnection:
    def __init__(self, message=None, error=False):
        self.message, self.error, self.closed = message, error, False

    async def __aenter__(self):
        if self.error:
            raise OSError("synthetic network failure")
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def recv(self):
        if self.message is not None:
            result, self.message = self.message, None
            return result
        await asyncio.sleep(10)


def validate_manifest(folder):
    manifest = json.loads((folder / "manifest.json").read_text())
    for name, digest in manifest["files_sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
    return json.loads((folder / "report.json").read_text())


async def test_duration_stops_socket_and_writes_integrity_manifest(tmp_path):
    connection = FakeConnection(payload())
    folder = tmp_path / "capture"
    await capture(folder, seconds=0.5, connector=lambda *a, **k: connection)
    report = validate_manifest(folder)
    assert report["stop_reason"] == "duration_limit"
    assert report["messages"] == 1 and connection.closed
    assert sum(p.stat().st_size for p in folder.iterdir()) <= 50_000_000
    assert verify(folder)["verified"]
    path = next(folder.glob("messages-*.jsonl"))
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(AssertionError):
        verify(folder)


async def test_failed_connection_has_bounded_attempts(tmp_path):
    folder = tmp_path / "capture"
    await capture(
        folder, seconds=1, max_attempts=1, connector=lambda *a, **k: FakeConnection(error=True)
    )
    report = validate_manifest(folder)
    assert report["stop_reason"] == "attempt_limit" and report["attempts"] == 1
    assert report["messages"] == 0


async def test_byte_limit_stops_and_records_unpersisted_message(tmp_path):
    folder = tmp_path / "capture"
    connection = FakeConnection("x" * 1_000_000)
    await capture(folder, seconds=1, max_bytes=1_000_000, connector=lambda *a, **k: connection)
    report = validate_manifest(folder)
    assert report["stop_reason"] == "byte_limit" and report["messages"] == 0
    assert connection.closed


async def test_cancel_closes_socket_and_keeps_manifest(tmp_path):
    folder = tmp_path / "capture"
    connection = FakeConnection(payload())
    task = asyncio.create_task(capture(folder, seconds=1, connector=lambda *a, **k: connection))
    await asyncio.sleep(0.02)
    task.cancel()
    await task
    assert validate_manifest(folder)["stop_reason"] == "cancelled"
    assert connection.closed


async def test_stop_marker_closes_socket_and_preserves_verifiable_capture(tmp_path):
    marker = tmp_path / "session.stop"

    class StopConnection(FakeConnection):
        async def recv(self):
            marker.touch()
            return payload()

    connection = StopConnection()
    folder = tmp_path / "capture"
    await capture(folder, seconds=2, stop_file=marker, connector=lambda *a, **k: connection)
    assert connection.closed
    assert verify(folder)["stop_reason"] == "user_stop"
    assert validate_manifest(folder)["messages"] == 1


async def test_stop_marker_must_be_new_and_outside_capture(tmp_path):
    folder = tmp_path / "capture"
    with pytest.raises(ValueError, match="outside"):
        await capture(folder, stop_file=folder / "stop")
    marker = tmp_path / "existing.stop"
    marker.touch()
    with pytest.raises(ValueError, match="already exists"):
        await capture(folder, stop_file=marker)
    assert not folder.exists()
