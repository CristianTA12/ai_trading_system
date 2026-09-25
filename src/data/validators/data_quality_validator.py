"""Strict validation of complete monthly Binance spot 1m archives."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """Return a closed month's UTC half-open bounds."""
    try:
        start = datetime.strptime(month, "%Y-%m").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError("El mes debe tener formato YYYY-MM") from exc
    if start.strftime("%Y-%m") != month:
        raise ValueError("El mes debe tener formato YYYY-MM")
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    if end > datetime.now(UTC):
        raise ValueError("Selecciona un mes completo, anterior al mes actual")
    return start, end


def validate_candles(frame: pd.DataFrame, month: str) -> dict[str, Any]:
    """Report missing/invalid candles without silently filling or dropping rows."""
    start, end = month_bounds(month)
    expected = pd.date_range(start, end, freq="min", inclusive="left")
    times = pd.DatetimeIndex(frame["time"])
    values = frame[["open", "high", "low", "close", "volume", "trades"]]
    finite = pd.Series(np.isfinite(values.to_numpy(dtype=float)).all(axis=1), index=frame.index)
    prices_ok = (
        (frame[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (frame["high"] >= frame[["open", "low", "close"]].max(axis=1))
        & (frame["low"] <= frame[["open", "high", "close"]].min(axis=1))
    )
    activity_ok = (
        (frame["volume"] >= 0)
        & (frame["trades"] >= 0)
        & (frame["trades"] <= 2_147_483_647)
        & (frame["trades"] % 1 == 0)
    )
    aligned = (times.second == 0) & (times.microsecond == 0) & (times.nanosecond == 0)
    in_range = (times >= start) & (times < end)
    missing = expected.difference(times)
    invalid = ~(finite & prices_ok & activity_ok & aligned & in_range)
    duplicates = int(times.duplicated().sum())
    report = {
        "market": "spot",
        "symbol": "BTC/USDT",
        "exchange": "binance",
        "timeframe": "1m",
        "month": month,
        "rows": len(frame),
        "expected_rows": calendar.monthrange(start.year, start.month)[1] * 1440,
        "missing_minutes": len(missing),
        "duplicate_rows": duplicates,
        "invalid_rows": int(invalid.sum()),
        "ordered": bool(times.is_monotonic_increasing),
        "first_time": times.min().isoformat() if len(times) else None,
        "last_time": times.max().isoformat() if len(times) else None,
        "missing_sample": [t.isoformat() for t in missing[:10]],
        "invalid_row_sample": [int(i) + 1 for i in frame.index[invalid][:10]],
    }
    report["valid"] = bool(
        not len(missing) and not duplicates and not invalid.any() and report["ordered"]
    )
    return report
