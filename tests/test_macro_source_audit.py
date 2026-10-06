"""Reject unbounded, corrupt or misleading macro snapshots before feature work."""

import pytest

from scripts.audit_macro_sources import audit, parse_snapshot, summarize


def test_null_is_preserved_and_weekday_absence_is_not_called_data_gap():
    frame = parse_snapshot(
        b"observation_date,SP500\n2023-12-22,10\n2023-12-25,.\n2023-12-26,11\n", "SP500"
    )
    report = summarize(frame)
    assert report["null_rows"] == 1
    assert report["max_calendar_gap_days"] == 4
    assert "2023-12-25" in report["weekdays_without_value_unclassified"]
    assert report["causal_15m_coverage"] is None
    assert not report["historical_available_at_verified"]


@pytest.mark.parametrize(
    "body",
    [
        "2024-01-01,10\n",
        "2025-01-01,10\n",
        "2019-10-31,10\n",
        "2023-01-01,10\n2023-01-01,10\n",
        "2023-01-02,10\n2023-01-01,11\n",
        "2023-01-01,inf\n",
        "2023-01-01,-1\n",
        "2023-01-01,.\n",
    ],
)
def test_bad_or_out_of_scope_response_rejected(body):
    with pytest.raises(ValueError):
        parse_snapshot(("DATE,SP500\n" + body).encode(), "SP500")


def test_failed_download_does_not_become_zero_coverage_or_pass(tmp_path):
    report = audit(tmp_path)
    assert not report["ready_for_experiment"]
    assert all(x["status"] == "raw_unavailable" for x in report["series"].values())
    assert all(x["causal_15m_coverage"] is None for x in report["series"].values())


def test_fetch_cannot_overwrite_existing_raw(tmp_path):
    with pytest.raises(FileExistsError):
        audit(tmp_path, fetch=True)
