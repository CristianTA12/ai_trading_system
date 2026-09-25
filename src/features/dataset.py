"""Causal 15-minute features built from complete spot minute bars.

The index is the time a closed bar becomes available, not its opening time.
Future outcomes are exported separately and never used by build_features.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2

from src.config.settings import PROJECT_ROOT, settings
from src.data.validators.data_quality_validator import month_bounds

STEP = pd.Timedelta(minutes=15)
FEATURE_VERSION = 1


def complete_bars(aggregated: pd.DataFrame) -> pd.DataFrame:
    """Reject partial aggregates; never interpolate absent source minutes."""
    if aggregated.index.has_duplicates or not aggregated.index.is_monotonic_increasing:
        raise ValueError("Las velas deben estar ordenadas y sin duplicados")
    valid = (
        (aggregated["source_minutes"] == 15)
        & (aggregated["first_minute"] == aggregated.index)
        & (aggregated["last_minute"] == aggregated.index + pd.Timedelta(minutes=14))
    )
    return aggregated.loc[valid, ["open", "high", "low", "close", "volume", "trades"]].copy()


def aggregate_minutes(minutes: pd.DataFrame) -> pd.DataFrame:
    """In-memory equivalent of the database aggregation, used in tests/imports."""
    if (
        minutes.index.tz is None
        or str(minutes.index.tz) != "UTC"
        or minutes.index.has_duplicates
        or not minutes.index.is_monotonic_increasing
    ):
        raise ValueError("Se requieren minutos UTC ordenados y únicos")
    if (minutes.index != minutes.index.floor("min")).any():
        raise ValueError("Minutos desalineados")
    grouped = minutes.assign(source_time=minutes.index).resample(
        "15min", label="left", closed="left", origin="epoch"
    )
    bars = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        trades=("trades", "sum"),
        source_minutes=("source_time", "size"),
        first_minute=("source_time", "min"),
        last_minute=("source_time", "max"),
    )
    return complete_bars(bars)


def _segment_features(bars: pd.DataFrame) -> pd.DataFrame:
    close, volume = bars["close"], bars["volume"]
    result = pd.DataFrame(index=bars.index)
    for periods in (1, 4, 16):
        result[f"return_{periods}"] = close.pct_change(periods, fill_method=None)
    result["log_return_1"] = np.log(close / close.shift(1))
    result["volatility_20"] = result["return_1"].rolling(20, min_periods=20).std(ddof=1)
    for periods in (20, 50):
        result[f"sma_distance_{periods}"] = (
            close / close.rolling(periods, min_periods=periods).mean() - 1
        )
        result[f"ema_distance_{periods}"] = (
            close / close.ewm(span=periods, adjust=False, min_periods=periods).mean() - 1
        )
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    total = gain + loss
    result["rsi_14_cutler"] = (100 * gain / total).where(total != 0, 50)
    true_range = pd.concat(
        [
            bars["high"] - bars["low"],
            (bars["high"] - close.shift(1)).abs(),
            (bars["low"] - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    true_range.iloc[0] = np.nan
    result["atr_14_sma_ratio"] = true_range.rolling(14, min_periods=14).mean() / close
    result["range_ratio"] = (bars["high"] - bars["low"]) / close
    result["body_ratio"] = (close - bars["open"]) / bars["open"]
    mean_volume = volume.rolling(20, min_periods=20).mean()
    std_volume = volume.rolling(20, min_periods=20).std(ddof=1)
    result["volume_relative_20"] = (volume / mean_volume).where(mean_volume != 0, 0)
    result["volume_zscore_20"] = ((volume - mean_volume) / std_volume).where(std_volume != 0, 0)
    mean_trades = bars["trades"].rolling(20, min_periods=20).mean()
    result["trades_relative_20"] = (bars["trades"] / mean_trades).where(mean_trades != 0, 0)
    available = bars.index + STEP
    hour = available.hour + available.minute / 60
    result["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    result["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    result["weekday_sin"] = np.sin(2 * np.pi * available.dayofweek / 7)
    result["weekday_cos"] = np.cos(2 * np.pi * available.dayofweek / 7)
    result.index = available
    result.index.name = "available_at"
    return result.replace([np.inf, -np.inf], np.nan).dropna()


def build_features(bars: pd.DataFrame) -> pd.DataFrame:
    if bars.empty:
        raise ValueError("No hay velas completas")
    if bars.index.tz is None or str(bars.index.tz) != "UTC":
        raise ValueError("Se requiere un índice UTC")
    if bars.index.has_duplicates or not bars.index.is_monotonic_increasing:
        raise ValueError("Las velas deben estar ordenadas y sin duplicados")
    if (bars.index != bars.index.floor("15min")).any():
        raise ValueError("Las velas deben estar alineadas a 15 minutos")
    numeric = bars[["open", "high", "low", "close", "volume", "trades"]]
    if (
        not np.isfinite(numeric.to_numpy(dtype=float)).all()
        or (bars[["open", "high", "low", "close"]] <= 0).any().any()
    ):
        raise ValueError("Velas con valores inválidos")
    segments = bars.index.to_series().diff().ne(STEP).cumsum()
    return pd.concat([_segment_features(group) for _, group in bars.groupby(segments)])


def build_labels(bars: pd.DataFrame, feature_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Gross next-bar outcome, separate from predictors. No costs or execution promise."""
    next_bars = bars.shift(-1)
    next_time = bars.index.to_series().shift(-1)
    consecutive = next_time == bars.index + STEP
    labels = pd.DataFrame(
        {
            "target_return_next_15m": next_bars["close"] / next_bars["open"] - 1,
            "entry_open": next_bars["open"],
            "exit_close": next_bars["close"],
            "label_end": next_time + STEP,
        },
        index=bars.index,
    )
    labels.index = bars.index + STEP
    labels.index.name = "available_at"
    labels = labels.loc[consecutive.to_numpy()]
    return labels.reindex(feature_index).dropna()


def temporal_splits(labels: pd.DataFrame, train_end: str, validation_end: str) -> pd.DataFrame:
    """Purge labels whose outcome reaches the next partition; no random split."""
    train_cut = pd.Timestamp(train_end, tz="UTC")
    validation_cut = pd.Timestamp(validation_end, tz="UTC")
    if train_cut >= validation_cut:
        raise ValueError("train-end debe preceder validation-end")
    result = pd.DataFrame(index=labels.index)
    result["split"] = "test"
    result.loc[result.index < validation_cut, "split"] = "validation"
    result.loc[result.index < train_cut, "split"] = "train"
    cross_train = (result["split"] == "train") & (labels["label_end"] >= train_cut)
    cross_validation = (result["split"] == "validation") & (labels["label_end"] >= validation_cut)
    result.loc[cross_train | cross_validation, "split"] = "purged"
    return result


def export_dataset(
    start: str,
    end: str,
    output: Path | None = None,
    train_end: str = "2024-01-01",
    validation_end: str = "2025-01-01",
) -> dict:
    first, _ = month_bounds(start)
    _, stop = month_bounds(end)
    train_cut, validation_cut = (
        pd.Timestamp(train_end, tz="UTC"),
        pd.Timestamp(validation_end, tz="UTC"),
    )
    if not first < train_cut < validation_cut < stop:
        raise ValueError("Se requiere inicio < train-end < validation-end < fin del rango")
    destination = output or PROJECT_ROOT / "data" / "processed" / (
        f"btc-usdt-spot-15m-v{FEATURE_VERSION}-{start}-{end}-"
        + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    if destination.exists():
        raise ValueError(
            "El destino ya existe: usa otro --output para conservar el dataset anterior"
        )
    query = """SELECT time_bucket('15 minutes', time) AS bar_open_time,
        first(open,time) AS open, max(high) AS high, min(low) AS low, last(close,time) AS close,
        sum(volume) AS volume, sum(trades) AS trades, count(*) AS source_minutes,
        min(time) AS first_minute, max(time) AS last_minute FROM ohlcv
        WHERE symbol='BTC/USDT' AND exchange='binance_spot' AND timeframe='1m'
        AND time >= %s AND time < %s GROUP BY 1 ORDER BY 1"""
    connection = psycopg2.connect(settings.database.url, connect_timeout=10)
    try:
        with connection, connection.cursor() as cursor:
            cursor.execute("SET TIME ZONE 'UTC'")
            cursor.execute(query, (first, stop))
            aggregated = pd.DataFrame(
                cursor.fetchall(), columns=[c.name for c in cursor.description]
            )
    finally:
        connection.close()
    if aggregated.empty:
        raise ValueError("No hay datos en el rango solicitado")
    for column in ("bar_open_time", "first_minute", "last_minute"):
        aggregated[column] = pd.to_datetime(aggregated[column], utc=True)
    aggregated = aggregated.set_index("bar_open_time")
    expected_months = set(pd.date_range(first, stop, freq="MS", inclusive="left").strftime("%Y-%m"))
    missing_months = sorted(expected_months - set(aggregated.index.strftime("%Y-%m")))
    if missing_months:
        raise ValueError("Faltan meses completos en la base de datos: " + ", ".join(missing_months))
    for column in ("open", "high", "low", "close", "volume", "trades"):
        aggregated[column] = aggregated[column].astype(float)
    bars = complete_bars(aggregated)
    features = build_features(bars)
    labels = build_labels(bars, features.index)
    splits = temporal_splits(labels, train_end, validation_end)
    if not {"train", "validation", "test"}.issubset(set(splits["split"])):
        raise ValueError("Alguna partición no tiene filas; amplía datos o ajusta los cortes")
    expected_minutes = int((stop - first).total_seconds() / 60)
    metadata = {
        "feature_version": FEATURE_VERSION,
        "recipe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "libraries": {name: version(name) for name in ("pandas", "numpy", "pyarrow")},
        "created_at": datetime.now(UTC).isoformat(),
        "symbol": "BTC/USDT",
        "exchange": "binance_spot",
        "timeframe": "15m",
        "start": start,
        "end": end,
        "source_minutes": int(aggregated["source_minutes"].sum()),
        "missing_source_minutes": expected_minutes - int(aggregated["source_minutes"].sum()),
        "expected_bars": expected_minutes // 15,
        "complete_bars": len(bars),
        "excluded_incomplete_or_absent_bars": expected_minutes // 15 - len(bars),
        "feature_rows": len(features),
        "warmup_excluded_bars": len(bars) - len(features),
        "label_rows": len(labels),
        "features_without_next_bar": len(features) - len(labels),
        "feature_columns": list(features.columns),
        "train_end": train_end,
        "validation_end": validation_end,
        "split_rows": splits["split"].value_counts().to_dict(),
        "availability": "bar_open_time + 15min (closed bar)",
        "execution_assumption": "next open; labels are gross, no fees/slippage included",
        "gap_policy": "no filling; drop partial bars; restart all rolling/EWM indicators after gaps",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as work:
        staged = Path(work) / "dataset"
        staged.mkdir()
        hashes = {}
        for name, frame in [
            ("bars", bars),
            ("features", features),
            ("labels", labels),
            ("splits", splits),
        ]:
            file = staged / f"{name}.parquet"
            frame.to_parquet(file, engine="pyarrow")
            with file.open("rb") as stream:
                hashes[file.name] = hashlib.file_digest(stream, "sha256").hexdigest()
        metadata["sha256"] = hashes
        (staged / "metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        staged.rename(destination)
    return {**metadata, "output": str(destination)}
