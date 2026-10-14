import json
from copy import deepcopy
from decimal import Decimal

from src.data.collectors.aggregate_prospective import aggregate_asof

START = 1609459200000
MINUTE = 60000


def rows(count=60):
    result = []
    for i in range(count):
        t = START + i * MINUTE
        k = {
            "t": t,
            "T": t + MINUTE - 1,
            "s": "BTCUSDT",
            "i": "1m",
            "x": True,
            "o": str(100 + i),
            "c": str(101 + i),
            "h": str(102 + i),
            "l": str(99 + i),
            "v": "0.1",
            "q": "10.1",
            "V": "0.03",
            "Q": "3.03",
            "n": i,
        }
        result.append(
            {
                "encoding": "text",
                "sequence": i + 1,
                "received_at_ns": (t + MINUTE + 1000) * 1000000,
                "payload": json.dumps({"e": "kline", "s": "BTCUSDT", "E": t + MINUTE, "k": k}),
            }
        )
    return result


def test_complete_utc_bars_ohlcv_taker_and_provenance():
    records = rows()
    result = aggregate_asof(records, records[-1]["received_at_ns"] + 1)
    assert list(result["15m"]) == [START + i * 15 * MINUTE for i in range(4)]
    hour = result["1h"][START]
    k = hour["kline"]
    assert (k["o"], k["c"], k["h"], k["l"]) == ("100", "160", "161", "99")
    assert k["T"] == START + 60 * MINUTE - 1
    assert k["i"] == "1h" and k["n"] == sum(range(60))
    for field, expected in {"v": "6", "q": "606", "V": "1.8", "Q": "181.8"}.items():
        assert Decimal(k[field]) == Decimal(expected)
    assert [s["sequence"] for s in hour["sources"]] == list(range(1, 61))
    assert hour["available_at_ns"] == records[-1]["received_at_ns"]


def test_exact_receipt_boundary_and_late_missing_minute():
    records = rows()
    late = records.pop(7)
    late["received_at_ns"] = records[-1]["received_at_ns"] + 1000000
    late["sequence"] = 61
    records.append(late)
    before = aggregate_asof(records, late["received_at_ns"])
    assert START not in before["15m"] and before["1h"] == {}
    assert len(before["15m"]) == 3
    after = aggregate_asof(records, late["received_at_ns"] + 1)
    assert after["1h"][START]["available_at_ns"] == late["received_at_ns"]


def test_revision_changes_only_later_decisions_without_double_counting():
    records = rows()
    decision = records[-1]["received_at_ns"] + 1
    baseline = aggregate_asof(records, decision)
    revision = deepcopy(records[4])
    value = json.loads(revision["payload"])
    value["k"]["v"] = "0.2"
    revision.update(payload=json.dumps(value), sequence=61, received_at_ns=decision + 100)
    records.append(revision)
    assert aggregate_asof(records, decision) == baseline
    assert aggregate_asof(records, revision["received_at_ns"]) == baseline
    changed = aggregate_asof(records, revision["received_at_ns"] + 1)
    assert Decimal(changed["1h"][START]["kline"]["v"]) == Decimal("6.1")
    assert changed["1h"][START]["sources"][4]["sequence"] == 61


def test_open_invalid_and_partial_minutes_cannot_fill_a_gap():
    records = rows()
    value = json.loads(records[1]["payload"])
    value["k"]["x"] = False
    records[1]["payload"] = json.dumps(value)
    records.append({"encoding": "text", "payload": "bad", "received_at_ns": 0})
    result = aggregate_asof(records, 10**30)
    assert START not in result["15m"] and result["1h"] == {}
    assert aggregate_asof(rows(10), 10**30) == {"15m": {}, "1h": {}}
    assert aggregate_asof([], 10**30) == {"15m": {}, "1h": {}}


def test_out_of_order_market_minutes_duplicates_and_utc_alignment():
    records = rows(75)
    records = records[1:]  # partial first quarter cannot become a rolling 15m bar
    records[4], records[5] = records[5], records[4]
    duplicate = deepcopy(records[-1])
    duplicate["sequence"] = 76
    duplicate["received_at_ns"] += 1
    records.append(duplicate)
    result = aggregate_asof(records, 10**30)
    assert list(result["15m"]) == [START + i * 15 * MINUTE for i in range(1, 5)]
    assert result["1h"] == {}
    assert Decimal(result["15m"][START + 60 * MINUTE]["kline"]["v"]) == Decimal("1.5")
