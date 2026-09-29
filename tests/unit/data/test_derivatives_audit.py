import pandas as pd

from scripts.audit_derivatives import availability


def test_availability_strict_boundary_and_expiry():
    events = pd.to_datetime(["2022-01-01 00:00Z"])
    decisions = pd.to_datetime(
        [
            "2022-01-01 00:00Z",
            "2022-01-01 00:15Z",
            "2022-01-01 00:30Z",
            "2022-01-01 00:45Z",
        ]
    )
    assert availability(decisions, events, "15min").tolist() == [False, False, True, False]


def test_availability_cannot_use_future_observation():
    decisions = pd.date_range("2022-01-01", periods=3, freq="15min", tz="UTC")
    future = pd.to_datetime(["2022-01-02 00:00Z"])
    assert not availability(decisions, future, "8h").any()


def test_availability_retains_millisecond_timestamp():
    events = pd.to_datetime(["2022-01-01 00:00:00.002Z"])
    decisions = pd.to_datetime(["2022-01-01 00:15Z", "2022-01-01 00:30Z"])
    assert availability(decisions, events, "15min").tolist() == [False, True]
