import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts.audit_sp500_api import END, START, request, summarize


def test_http_error_remains_error_not_empty_valid_dataset():
    result = summarize(
        json.dumps({"error_code": 400, "error_message": "Not in ALFRED"}),
        400,
        "observations",
        "2023-01-13",
    )
    assert result["status"] == "http_error"
    assert result["error_code"] == 400


@pytest.mark.parametrize(
    "dates,count", [(["2024-01-01"], 1), (["2023-01-13"], 2), (["2023-01-13", "2023-01-13"], 2)]
)
def test_vintage_list_requires_complete_bounded_unique_dates(dates, count):
    payload = {
        "vintage_dates": dates,
        "count": count,
        "offset": 0,
        "realtime_start": START,
        "realtime_end": END,
    }
    with pytest.raises(ValueError):
        summarize(json.dumps(payload), 200, "vintagedates")


def test_http_error_body_preserved_without_secret_in_argv(monkeypatch):
    key = "a" * 32

    def run(args, **kwargs):
        assert key not in str(args)
        assert key.encode() in kwargs["input"]
        assert "--location" not in args and "--insecure" not in args
        return SimpleNamespace(returncode=0, stdout=b'{"error_code":400}\n400')

    monkeypatch.setattr(subprocess, "run", run)
    raw, status = request("observations", {"series_id": "SP500"}, key, "curl")
    assert status == 400 and json.loads(raw)["error_code"] == 400


def test_secret_echo_refused(monkeypatch):
    key = "a" * 32
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=key.encode() + b"\n400"),
    )
    with pytest.raises(RuntimeError, match="refusing persistence"):
        request("observations", {}, key, "curl")
