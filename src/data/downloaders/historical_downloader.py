"""Download, verify and load Binance monthly BTC/USDT spot candles."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from src.config.settings import PROJECT_ROOT, settings
from src.data.validators.data_quality_validator import month_bounds, validate_candles

BASE_URL = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m"
COLUMNS = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "taker_base",
    "taker_quote",
    "ignore",
]


def default_month() -> str:
    return (datetime.now(UTC).replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def archive_path(month: str, raw_dir: Path | None = None) -> Path:
    month_bounds(month)
    root = raw_dir or Path(os.getenv("RAW_DATA_DIR", str(PROJECT_ROOT / "data" / "raw")))
    return root / "binance" / "spot" / "BTCUSDT" / "1m" / f"BTCUSDT-1m-{month}.zip"


def _fetch(url: str, destination: Path, limit: int = 100_000_000) -> None:
    """Bounded streaming download, retrying temporary failures; atomic replacement."""
    for attempt in range(3):
        temporary = None
        try:
            with (
                urlopen(url, timeout=60) as response,
                tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream,
            ):
                temporary = Path(stream.name)
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise ValueError("Archivo remoto demasiado grande")
                    stream.write(chunk)
            temporary.replace(destination)
            return
        except (URLError, TimeoutError, ConnectionError) as exc:
            if isinstance(exc, HTTPError) and exc.code == 404:
                raise ValueError("El archivo mensual todavía no está publicado en Binance") from exc
            if attempt == 2:
                raise ValueError("No se pudo descargar el archivo de Binance") from exc
            time.sleep(2**attempt)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def verify_checksum(path: Path) -> str:
    checksum = path.with_suffix(".zip.CHECKSUM")
    if not path.is_file() or not checksum.is_file():
        raise ValueError("Falta el ZIP o su .CHECKSUM; ejecuta download-historical primero")
    parts = checksum.read_text(encoding="utf-8").split()
    if (
        len(parts) != 2
        or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0])
        or parts[1].lstrip("*") != path.name
    ):
        raise ValueError("Formato o nombre de archivo incorrecto en .CHECKSUM")
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != parts[0].lower():
        raise ValueError("Checksum SHA-256 incorrecto; usa --refresh para volver a descargar")
    return actual


def download_archive(month: str, raw_dir: Path | None = None, refresh: bool = False) -> Path:
    path = archive_path(month, raw_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if refresh or not path.exists() or not path.with_suffix(".zip.CHECKSUM").exists():
        # Verify a complete new pair before replacing a previously valid cache.
        with tempfile.TemporaryDirectory(dir=path.parent) as work:
            staged = Path(work) / path.name
            _fetch(f"{BASE_URL}/{path.name}.CHECKSUM", staged.with_suffix(".zip.CHECKSUM"), 4096)
            _fetch(f"{BASE_URL}/{path.name}", staged)
            verify_checksum(staged)
            staged.replace(path)
            staged.with_suffix(".zip.CHECKSUM").replace(path.with_suffix(".zip.CHECKSUM"))
    verify_checksum(path)
    return path


def read_archive(path: Path, month: str) -> pd.DataFrame:
    """Parse timestamps explicitly: spot switches from ms to us in January 2025."""
    month_bounds(month)
    try:
        with ZipFile(path) as archive:
            if archive.namelist() != [path.with_suffix(".csv").name]:
                raise ValueError("El ZIP debe contener únicamente el CSV esperado")
            entry = archive.infolist()[0]
            if entry.file_size > 100_000_000:
                raise ValueError("CSV demasiado grande")
            with archive.open(entry) as stream:
                frame = pd.read_csv(stream, header=None, dtype=str)
        if frame.shape[1] != 12:
            raise ValueError("Se esperaban 12 columnas Binance spot")
        frame.columns = COLUMNS
        for column in [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trades",
            "close_time",
        ]:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        if (frame["timestamp"] % 1 != 0).any() or (frame["close_time"] % 1 != 0).any():
            raise ValueError("Timestamps fraccionarios")
        unit = "us" if month >= "2025-01" else "ms"
        frame["time"] = pd.to_datetime(frame["timestamp"], unit=unit, utc=True)
        expected_duration = 60_000_000 - 1 if unit == "us" else 60_000 - 1
        if ((frame["close_time"] - frame["timestamp"]) != expected_duration).any():
            raise ValueError("Duración de vela incorrecta o vela sin cerrar")
        return frame[["time", "open", "high", "low", "close", "volume", "trades"]]
    except (BadZipFile, pd.errors.ParserError, pd.errors.EmptyDataError, OverflowError) as exc:
        raise ValueError("Archivo de velas inválido") from exc


def validate_archive(month: str, raw_dir: Path | None = None) -> tuple[pd.DataFrame, dict]:
    path = archive_path(month, raw_dir)
    digest = verify_checksum(path)
    frame = read_archive(path, month)
    report = validate_candles(frame, month)
    report.update(sha256=digest, source=f"{BASE_URL}/{path.name}")
    path.with_suffix(".report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return frame, report


def load_month(month: str, raw_dir: Path | None = None) -> dict:
    frame, report = validate_archive(month, raw_dir)
    if not report["valid"]:
        raise ValueError("Validación rechazada: " + json.dumps(report))
    # Explicit namespace prevents future spot/futures collisions in the existing schema.
    rows = [
        (
            r.time.to_pydatetime(),
            "BTC/USDT",
            "binance_spot",
            "1m",
            float(r.open),
            float(r.high),
            float(r.low),
            float(r.close),
            float(r.volume),
            int(r.trades),
        )
        for r in frame.itertuples()
    ]
    query = """
        INSERT INTO ohlcv (time, symbol, exchange, timeframe, open, high, low, close, volume, trades)
        VALUES %s ON CONFLICT (time, symbol, exchange, timeframe) DO UPDATE SET
        open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
        close=EXCLUDED.close, volume=EXCLUDED.volume, trades=EXCLUDED.trades
        WHERE (ohlcv.open,ohlcv.high,ohlcv.low,ohlcv.close,ohlcv.volume,ohlcv.trades)
        IS DISTINCT FROM (EXCLUDED.open,EXCLUDED.high,EXCLUDED.low,EXCLUDED.close,EXCLUDED.volume,EXCLUDED.trades)
    """
    written = 0
    connection = psycopg2.connect(settings.database.url, connect_timeout=10)
    try:
        with connection, connection.cursor() as cursor:
            # One transaction for the whole month, batches reduce HDD round trips.
            for offset in range(0, len(rows), 2000):
                execute_values(cursor, query, rows[offset : offset + 2000], page_size=2000)
                written += cursor.rowcount
    finally:
        connection.close()
    return {**report, "database_exchange": "binance_spot", "written_rows": written}
