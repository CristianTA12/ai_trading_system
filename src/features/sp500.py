"""SP500 features conditional on an explicitly accepted current-snapshot/+48h assumption."""

import hashlib
import io
from pathlib import Path

import numpy as np
import pandas as pd

SP500_COLUMNS = ["sp500_return_1d", "sp500_sma_distance_20", "sp500_data_age_hours"]
SNAPSHOT_SHA256 = "5921ef639046179df0d2c1029ee977d5d42fc3173c861a69e72273d059faf8eb"


def load_sp500(path: Path) -> pd.Series:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SNAPSHOT_SHA256:
        raise ValueError("SP500 snapshot differs from preregistered input")
    frame = pd.read_csv(io.BytesIO(raw), na_values=["."])
    if frame.columns.tolist() != ["observation_date", "SP500"]:
        raise ValueError("Unexpected SP500 schema")
    dates = pd.to_datetime(frame.observation_date, format="%Y-%m-%d", utc=True)
    return pd.Series(pd.to_numeric(frame.SP500).to_numpy(), index=dates, name="close")


def observation_states(closes: pd.Series) -> pd.DataFrame:
    index = closes.index
    if (
        not isinstance(index, pd.DatetimeIndex)
        or index.tz is None
        or index.empty
        or index.has_duplicates
        or index.hasnans
        or not index.is_monotonic_increasing
    ):
        raise ValueError("SP500 requires sorted unique timezone-aware dates")
    index = index.tz_convert("UTC")
    if (
        not index.equals(index.normalize())
        or index.min() < pd.Timestamp("2019-11-01", tz="UTC")
        or index.max() >= pd.Timestamp("2024-01-01", tz="UTC")
    ):
        raise ValueError("SP500 outside bounded UTC observation-date window")
    values = closes.dropna()
    if values.empty or not np.isfinite(values.to_numpy()).all() or values.le(0).any():
        raise ValueError("Invalid SP500 closes")
    # Distinct observed sessions, never repeated 15-minute bars or forward-filled holidays.
    states = pd.DataFrame(
        {"observation_date": values.index.tz_convert("UTC"), "sp500_close": values.to_numpy()}
    )
    states["assumed_available_at"] = states.observation_date + pd.Timedelta(hours=48)
    states[SP500_COLUMNS[0]] = states.sp500_close.pct_change(fill_method=None)
    states[SP500_COLUMNS[1]] = states.sp500_close / states.sp500_close.rolling(20).mean() - 1
    return states


def align_sp500(index: pd.DatetimeIndex, closes: pd.Series) -> pd.DataFrame:
    if (
        not isinstance(index, pd.DatetimeIndex)
        or index.tz is None
        or index.empty
        or index.has_duplicates
        or index.hasnans
        or not index.is_monotonic_increasing
    ):
        raise ValueError("Decisions require sorted unique timezone-aware timestamps")
    if index.min() < pd.Timestamp("2020-01-01", tz="UTC") or index.max() >= pd.Timestamp(
        "2024-01-01", tz="UTC"
    ):
        raise ValueError("Decisions outside 2020-2023 research window")
    decisions = index.tz_convert("UTC")
    states = observation_states(closes)
    aligned = pd.merge_asof(
        pd.DataFrame({"decision_at": decisions}),
        states,
        left_on="decision_at",
        right_on="assumed_available_at",
        direction="backward",
        allow_exact_matches=False,
    ).set_index("decision_at")
    aligned[SP500_COLUMNS[2]] = (aligned.index - aligned.observation_date).dt.total_seconds() / 3600
    eligible = np.isfinite(aligned[SP500_COLUMNS]).all(axis=1) & aligned[SP500_COLUMNS[2]].between(
        0, 168
    )
    aligned["eligible_under_assumption"] = eligible
    aligned.loc[~eligible, SP500_COLUMNS] = np.nan
    aligned.index = index
    return aligned
