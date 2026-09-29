"""Funding eligibility must never depend on future or repeated bar observations."""

import numpy as np
import pandas as pd
import pytest

from src.backtesting.dataset import ExperimentData
from src.features.funding import FUNDING_COLUMNS, align_funding, build_funding_features
from src.training.regime_experiment import paired_folds


def events(times=None):
    times = (
        pd.to_datetime(times, utc=True, format="ISO8601")
        if times is not None
        else pd.date_range("2020-01-01", periods=4, freq="8h", tz="UTC")
    )
    return pd.DataFrame(
        {
            "time": times,
            "last_funding_rate": [0.01, 0.02, -0.03, 0.04][: len(times)],
            "funding_interval_hours": 8,
        }
    )


def test_strict_availability_and_millisecond_precision():
    data = events(["2020-01-01T00:00:00.002Z"])
    index = pd.to_datetime(
        ["2020-01-01T00:15:00Z", "2020-01-01T00:15:00.002Z", "2020-01-01T00:15:00.003Z"],
        utc=True,
        format="ISO8601",
    )
    result = align_funding(index, data)
    assert result.funding_last_settled.iloc[:2].isna().all()
    assert result.funding_last_settled.iloc[2] == 0.01


def test_expiry_boundary_no_indefinite_fill():
    index = pd.to_datetime(
        ["2020-01-01T08:15:00Z", "2020-01-01T08:15:00.001Z"], utc=True, format="ISO8601"
    )
    result = align_funding(index, events().iloc[:1])
    assert result.funding_last_settled.iloc[0] == 0.01
    assert result.funding_last_settled.iloc[1:].isna().all()


def test_event_mean_not_bar_mean_and_future_invariance():
    index = pd.date_range("2020-01-01", periods=96, freq="15min", tz="UTC")
    result = align_funding(index, events())
    assert result.loc[:"2020-01-01 16:15", "funding_mean_3_events"].isna().all()
    assert result.loc["2020-01-01 16:30", "funding_delta_event"] == pytest.approx(-0.05)
    assert result.loc["2020-01-01 16:30", "funding_mean_3_events"] == pytest.approx(0)
    changed = events()
    changed.loc[3, "last_funding_rate"] = 999
    pd.testing.assert_frame_equal(result, align_funding(index, changed))
    pd.testing.assert_frame_equal(result, align_funding(index, events().iloc[:3]))


def test_gap_resets_history():
    data = events(
        ["2020-01-01T00:00Z", "2020-01-01T08:00Z", "2020-01-02T00:00Z", "2020-01-02T08:00Z"]
    )
    index = pd.to_datetime(["2020-01-02T00:30Z", "2020-01-02T08:30Z"], utc=True, format="ISO8601")
    result = align_funding(index, data)
    assert result.funding_mean_3_events.isna().all()
    assert np.isnan(result.funding_delta_event.iloc[0])
    assert result.funding_delta_event.iloc[1] == pytest.approx(0.07)


@pytest.mark.parametrize("invalid", ["duplicate", "nonfinite", "interval", "unsorted"])
def test_invalid_events_rejected(invalid):
    data = events()
    if invalid == "duplicate":
        data.loc[1, "time"] = data.loc[0, "time"]
    elif invalid == "nonfinite":
        data.loc[1, "last_funding_rate"] = np.inf
    elif invalid == "interval":
        data.loc[1, "funding_interval_hours"] = 4
    else:
        data = data.iloc[::-1]
    with pytest.raises(ValueError):
        align_funding(pd.date_range("2020-01-01", periods=2, tz="UTC"), data)


def test_complete_case_warmup_preserves_v1():
    index = pd.date_range("2020-01-01 12:30", periods=32, freq="15min", tz="UTC")
    v1 = pd.DataFrame({"original": np.arange(len(index))}, index=index)
    result = build_funding_features(v1, events())
    assert len(v1) - len(result) == 16
    assert list(result.columns) == ["original", *FUNDING_COLUMNS]
    pd.testing.assert_series_equal(result.original, v1.loc[result.index, "original"])


def test_paired_rows_purge_and_execution_gaps():
    index = pd.date_range("2020-01-01", "2024-01-01", freq="15min", inclusive="left", tz="UTC")
    v1 = pd.DataFrame({"original": 1.0}, index=index)
    bars = pd.DataFrame({"open": 100.0, "close": 100.0}, index=index)
    data = ExperimentData(
        {"train_end": "2024-01-01"},
        v1,
        pd.Series(0.0, index=index),
        v1.iloc[:0],
        pd.Series(dtype=float),
        bars.iloc[:0],
        v1.iloc[:0],
        bars,
    )
    # A missing signal inside eval must not remove an execution bar.
    missing = pd.Timestamp("2022-03-01", tz="UTC")
    features = v1.iloc[16:].drop(index=missing).assign(funding=0.01)
    for name, control, candidate in paired_folds(data, features):
        assert control.train_features.index.equals(candidate.train_features.index)
        assert control.validation_features.index.equals(candidate.validation_features.index)
        assert control.train_returns.equals(candidate.train_returns)
        assert control.validation_returns.equals(candidate.validation_returns)
        assert (
            control.train_features.index + pd.Timedelta(minutes=15) < pd.Timestamp(name, tz="UTC")
        ).all()
        if name == "2022-01-01":
            assert missing in control.validation_bars.index
            assert missing not in control.validation_features.index
