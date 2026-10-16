import json

import pytest

from src.data.collectors import campaign


@pytest.mark.parametrize(
    "stop_reason,expected_sessions", [("duration_limit", 3), ("attempt_limit", 1), ("user_stop", 1)]
)
async def test_campaign_bounds_and_stops_on_failure(
    tmp_path, monkeypatch, stop_reason, expected_sessions
):
    clock = [0.0]
    durations = []
    monkeypatch.setattr(campaign.time, "monotonic", lambda: clock[0])

    async def fake_capture(folder, seconds, stop_file):
        durations.append(seconds)
        assert 0 < seconds <= 7200
        assert not stop_file.is_relative_to(folder)
        folder.mkdir()
        report = {
            "ended_at_ns": 1,
            "messages": 1,
            "stop_reason": stop_reason,
            "missing_closed_minutes": [],
        }
        (folder / "report.json").write_text(json.dumps(report))
        clock[0] += seconds + 5

    monkeypatch.setattr(campaign, "capture", fake_capture)
    monkeypatch.setattr(campaign, "verify", lambda folder: {"verified": True})
    code = await campaign.run(tmp_path / "campaign")
    assert len(durations) == expected_sessions
    assert sum(durations) <= 18000
    assert code == (2 if stop_reason == "attempt_limit" else 0)
    result = json.loads((tmp_path / "campaign/result.json").read_text())
    assert result["stop_reason"] == stop_reason
    assert not result["continuous_coverage_claimed"]
