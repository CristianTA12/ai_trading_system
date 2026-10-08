"""Closed-bar aggressor imbalance with one full bar of assumed delivery margin."""

import numpy as np
import pandas as pd

from src.backtesting.engine import validate_index

FLOW_COLUMNS = ["flow_imbalance_15m", "flow_imbalance_1h"]
STEP = pd.Timedelta(minutes=15)


def aggregate_flow(minutes: pd.DataFrame) -> pd.DataFrame:
    validate_index(minutes.index)
    if minutes.empty or (minutes.index != minutes.index.floor("min")).any():
        raise ValueError("Nonempty minute grid required")
    values = minutes[["volume", "taker_base"]]
    if (
        not np.isfinite(values.to_numpy()).all()
        or (values < 0).any().any()
        or (minutes.taker_base > minutes.volume).any()
    ):
        raise ValueError("Invalid aggressor volume")
    result = minutes.resample("15min", closed="left", label="left").agg(
        volume=("volume", "sum"),
        taker_base=("taker_base", "sum"),
        source_minutes=("volume", "size"),
    )
    return result.loc[result.source_minutes.eq(15)].copy()


def align_flow(decisions: pd.DatetimeIndex, bars: pd.DataFrame) -> pd.DataFrame:
    validate_index(decisions)
    validate_index(bars.index)
    if (decisions != decisions.floor("15min")).any() or (
        bars.index != bars.index.floor("15min")
    ).any():
        raise ValueError("15 minute grid required")
    latest = decisions - 2 * STEP
    recent = bars.reindex(latest)
    result = pd.DataFrame(index=decisions)
    result[FLOW_COLUMNS[0]] = (
        (2 * recent.taker_base - recent.volume) / recent.volume.where(recent.volume > 0)
    ).to_numpy()
    sums = np.zeros((len(decisions), 2))
    complete = np.ones(len(decisions), dtype=bool)
    for offset in range(4):
        values = bars.reindex(latest - offset * STEP)[["volume", "taker_base"]].to_numpy()
        complete &= np.isfinite(values).all(axis=1)
        sums += values
    denominator = np.where(complete & (sums[:, 0] > 0), sums[:, 0], np.nan)
    result[FLOW_COLUMNS[1]] = (2 * sums[:, 1] - sums[:, 0]) / denominator
    result["latest_source_open"] = latest
    result["latest_source_close"] = latest + STEP
    result["eligible_under_assumption"] = np.isfinite(result[FLOW_COLUMNS]).all(axis=1)
    return result
