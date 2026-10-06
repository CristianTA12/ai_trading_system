import subprocess
from types import SimpleNamespace

import pytest

from scripts.audit_macro_sources import fetch_csv
from scripts.audit_macro_vintages import compare_vintage


def test_vintage_revision_is_measured_without_claiming_publication_hour():
    old = b"observation_date,VIXCLS_20230110\n2023-01-09,20\n2023-01-10,21\n"
    new = b"observation_date,VIXCLS\n2023-01-09,20.1\n2023-01-10,21\n"
    result = compare_vintage(old, new, "VIXCLS", "2023-01-10")
    assert result["changed_values"] == 1
    assert result["max_abs_revision"] == pytest.approx(0.1)
    assert not result["intraday_availability_proven"]


@pytest.mark.parametrize(
    "header,day", [("VIXCLS_20230111", "2023-01-09"), ("VIXCLS_20230110", "2023-01-11")]
)
def test_ignored_vintage_parameter_is_rejected(header, day):
    raw = f"observation_date,{header}\n{day},20\n".encode()
    latest = b"observation_date,VIXCLS\n2023-01-09,20\n"
    with pytest.raises(ValueError):
        compare_vintage(raw, latest, "VIXCLS", "2023-01-10")


def test_curl_uses_verified_https_and_timeouts(monkeypatch):
    def fake_run(args, **kwargs):
        assert "--max-time" in args and "--connect-timeout" in args
        assert "--insecure" not in args and "-k" not in args
        assert kwargs["timeout"] == 30 and kwargs["check"]
        return SimpleNamespace(stdout=b"raw")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert fetch_csv("https://fred.stlouisfed.org/example", "curl") == b"raw"


def test_curl_failures_do_not_become_csv(monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(22, ["curl"])

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        fetch_csv("https://fred.stlouisfed.org/example", "curl")
