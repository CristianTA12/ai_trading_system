"""Settled funding features under an explicit, unverified 15-minute availability lag."""

import hashlib
import io
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from src.backtesting.engine import validate_index

FUNDING_COLUMNS = ["funding_last_settled", "funding_delta_event", "funding_mean_3_events"]


def load_audited_funding(folder: Path) -> pd.DataFrame:
    """Reconstruct the snapshot from checksum-verified archives; never download data."""
    manifest = pd.read_csv(folder / "manifest.csv")
    expected = {
        f"BTCUSDT-fundingRate-{month}.zip"
        for month in pd.period_range("2020-01", "2023-12", freq="M")
    }
    names = manifest.Key.map(lambda key: Path(key).name)
    if set(names) != expected or len(names) != 48:
        raise ValueError("Se requieren exactamente los 48 archivos funding 2020-2023")
    chunks = []
    for row in manifest.itertuples():
        path = folder / Path(row.Key).name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksum = path.with_suffix(".zip.CHECKSUM").read_text().split()
        if checksum != [digest, path.name] or digest != row.sha256:
            raise ValueError(f"Checksum funding incorrecto: {path.name}")
        with ZipFile(path) as archive:
            chunks.append(pd.read_csv(io.BytesIO(archive.read(path.with_suffix(".csv").name))))
    events = pd.concat(chunks, ignore_index=True)
    events["time"] = pd.to_datetime(events.calc_time, unit="ms", utc=True)
    events = events.sort_values("time").reset_index(drop=True)
    if not events.time.between(
        pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC"), inclusive="left"
    ).all():
        raise ValueError("Funding fuera de 2020-2023")
    snapshot = (
        pd.read_parquet(folder / "observations.parquet").sort_values("time").reset_index(drop=True)
    )
    pd.testing.assert_frame_equal(events, snapshot[events.columns])
    return events


def align_funding(index: pd.DatetimeIndex, events: pd.DataFrame) -> pd.DataFrame:
    """Compute event deltas/means BEFORE strict backward as-of alignment.

    Level expires 8h after assumed availability (8h15m after settlement).
    Missing nominal events reset the delta/mean history. Original milliseconds
    are retained for eligibility; nominal slots are used only to detect gaps.
    """
    validate_index(index)
    times = pd.DatetimeIndex(events.time)
    validate_index(times)
    if events.empty or not events.funding_interval_hours.eq(8).all():
        raise ValueError("Esta receta requiere eventos funding de 8h")
    rates = events.last_funding_rate.to_numpy(dtype=float)
    if not np.isfinite(rates).all():
        raise ValueError("Funding no finito")
    slots = times.floor("8h")
    if slots.has_duplicates:
        raise ValueError("Más de una liquidación en el mismo slot nominal")
    frame = pd.DataFrame({"event_time": times, "funding_last_settled": rates})
    segments = pd.Series(slots).diff().ne(pd.Timedelta(hours=8)).cumsum()
    grouped = frame.funding_last_settled.groupby(segments)
    frame["funding_delta_event"] = grouped.diff()
    frame["funding_mean_3_events"] = grouped.transform(lambda x: x.rolling(3).mean())
    frame["assumed_available_at"] = frame.event_time + pd.Timedelta(minutes=15)
    aligned = pd.merge_asof(
        pd.DataFrame({"decision_at": index}),
        frame,
        left_on="decision_at",
        right_on="assumed_available_at",
        direction="backward",
        allow_exact_matches=False,
        tolerance=pd.Timedelta(hours=8),
    ).set_index("decision_at")
    aligned.index.name = index.name
    return aligned


def build_funding_features(v1: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    aligned = align_funding(v1.index, events)
    return v1.join(aligned[FUNDING_COLUMNS]).dropna()
