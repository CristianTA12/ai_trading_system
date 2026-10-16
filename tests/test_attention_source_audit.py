import pytest

from scripts.audit_attention_source import inspect


def item():
    return {
        "project": "en.wikipedia",
        "article": "Bitcoin",
        "access": "all-access",
        "agent": "user",
        "granularity": "daily",
        "timestamp": "2020010100",
        "views": 7,
    }


def test_missing_days_remain_missing_and_no_publication_claim():
    report = inspect({"items": [item()]})
    assert report["observed_days"] == 1 and len(report["missing_days"]) == 30
    assert not report["causal_backtest_ready"] and not report["missing_values_filled"]


@pytest.mark.parametrize(
    "change", [{"views": -1}, {"views": True}, {"timestamp": "2025010100"}, {"agent": "all-agents"}]
)
def test_invalid_or_out_of_scope_records_rejected(change):
    with pytest.raises(ValueError):
        inspect({"items": [{**item(), **change}]})


def test_duplicate_days_rejected():
    with pytest.raises(ValueError):
        inspect({"items": [item(), item()]})
