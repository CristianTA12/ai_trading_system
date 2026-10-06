import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts.audit_vix_api import END, START, fetch, parse_response


def response():
    return {
        "realtime_start": "2023-01-13",
        "realtime_end": "2023-01-13",
        "observation_start": START,
        "observation_end": END,
        "count": 1,
        "offset": 0,
        "observations": [
            {
                "realtime_start": "2023-01-13",
                "realtime_end": "2023-01-13",
                "date": "2023-01-16",
                "value": "19.49",
            }
        ],
    }


def test_future_value_is_preserved_for_diagnosis():
    values = parse_response(json.dumps(response()), "2023-01-13")
    assert str(values.index[0].date()) == "2023-01-16"
    assert values.iloc[0] == 19.49


@pytest.mark.parametrize(
    "field,value",
    [
        ("realtime_start", "2023-01-14"),
        ("observation_end", "2024-01-01"),
        ("count", 2),
        ("offset", 1),
    ],
)
def test_wrong_window_or_incomplete_response_rejected(field, value):
    payload = response()
    payload[field] = value
    with pytest.raises(ValueError):
        parse_response(json.dumps(payload), "2023-01-13")


def test_key_only_in_stdin_and_never_in_saved_params(monkeypatch):
    key = "a" * 32

    def run(args, **kwargs):
        assert key not in str(args)
        assert key.encode() in kwargs["input"]
        assert "--location" not in args and "--insecure" not in args
        return SimpleNamespace(returncode=0, stdout=b"{}")

    monkeypatch.setattr(subprocess, "run", run)
    raw, params = fetch("2023-01-13", key, "curl")
    assert raw == b"{}"
    assert key not in str(params) and "api_key" not in params


def test_transport_exception_does_not_expose_secret(monkeypatch):
    key = "a" * 32

    def run(*args, **kwargs):
        raise subprocess.TimeoutExpired(key, 30, output=key)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RuntimeError) as caught:
        fetch("2023-01-13", key, "curl")
    assert key not in str(caught.value)


def test_echoed_credential_cannot_be_saved(monkeypatch):
    key = "a" * 32
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=key.encode())
    )
    with pytest.raises(RuntimeError, match="refusing persistence"):
        fetch("2023-01-13", key, "curl")
