import pytest

from src.data.collectors.hour_pilot import HOUR_NS, assess, plan
from src.data.collectors.prospective import capture


@pytest.mark.parametrize("offset", [0, 1, HOUR_NS // 2, HOUR_NS - 1])
def test_plan_includes_full_next_hour_and_bounded_close_margin(offset):
    now = 500000 * HOUR_NS + offset
    recipe = plan(now)
    assert recipe["target_start_ms"] == 500001 * HOUR_NS // 1000000
    assert recipe["target_end_exclusive_ms"] == 500002 * HOUR_NS // 1000000
    assert 3630 <= recipe["seconds"] <= 7230
    assert recipe["planned_stop_ns"] - now == pytest.approx(recipe["seconds"] * 1e9)


def test_verdict_needs_target_hour_and_clean_temporal_quality():
    recipe = plan(500000 * HOUR_NS)
    report = {
        "stop_reason": "duration_limit",
        "invalid_messages": 0,
        "wall_clock_jumps_over_1s": 0,
        "clock_synchronization": "unknown",
    }
    bars = {"15m": {}, "1h": {}}
    assert not assess(bars, report, recipe)["quality_pass"]
    bars["1h"][recipe["target_start_ms"]] = {"sources": list(range(60))}
    assert assess(bars, report, recipe)["quality_pass"]
    for key, value in (
        ("stop_reason", "attempt_limit"),
        ("invalid_messages", 1),
        ("wall_clock_jumps_over_1s", 1),
    ):
        assert not assess(bars, {**report, key: value}, recipe)["quality_pass"]


async def test_extended_capture_still_rejects_unbounded_duration(tmp_path):
    with pytest.raises(ValueError, match="7500"):
        await capture(tmp_path / "capture", seconds=7501)
    assert not (tmp_path / "capture").exists()
