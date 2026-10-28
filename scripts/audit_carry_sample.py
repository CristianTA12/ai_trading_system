"""Bounded pre-2024 spot/delivery-future schema audit, without return calculations."""

import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
import requests

BASE = "https://data.binance.vision/"
DAY = "2022-01-03"
CONTRACT = "BTCUSDT_220325"
KEYS = {
    "spot": f"data/spot/daily/klines/BTCUSDT/15m/BTCUSDT-15m-{DAY}.zip",
    "future": f"data/futures/um/daily/klines/{CONTRACT}/15m/{CONTRACT}-15m-{DAY}.zip",
    "mark": f"data/futures/um/daily/markPriceKlines/{CONTRACT}/15m/{CONTRACT}-15m-{DAY}.zip",
    "index": f"data/futures/um/daily/indexPriceKlines/BTCUSDT/15m/BTCUSDT-15m-{DAY}.zip",
}
LIMIT = 2_000_000


def inspect(body):
    with ZipFile(io.BytesIO(body)) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].file_size > LIMIT:
            raise ValueError("Unexpected archive size or members")
        table = pd.read_csv(io.BytesIO(archive.read(members[0])), header=None, dtype=str)
    if table.iloc[0, 0] in {"open_time", "openTime"}:
        table = table.iloc[1:].reset_index(drop=True)
    if table.shape[1] != 12:
        raise ValueError("Expected 12 kline fields")
    stamps = pd.to_datetime(pd.to_numeric(table[0]), unit="ms", utc=True)
    expected = pd.date_range(DAY, periods=96, freq="15min", tz="UTC")
    if stamps.duplicated().any() or not stamps.is_monotonic_increasing:
        raise ValueError("Duplicate or unordered timestamps")
    if not stamps.isin(expected).all():
        raise ValueError("Data outside fixed development day")
    prices = table[[1, 2, 3, 4]].astype(float)
    if not np.isfinite(prices).all().all() or (prices <= 0).any().any():
        raise ValueError("Invalid prices")
    if (prices[2] < prices.max(axis=1)).any() or (prices[3] > prices.min(axis=1)).any():
        raise ValueError("Invalid OHLC ordering")
    closes = pd.to_datetime(pd.to_numeric(table[6]), unit="ms", utc=True)
    if not (closes == stamps + pd.Timedelta(minutes=15) - pd.Timedelta(milliseconds=1)).all():
        raise ValueError("Unexpected close timestamps")
    return {
        "rows": len(table),
        "expected_rows": 96,
        "missing_rows": int((~expected.isin(stamps)).sum()),
        "columns": 12,
        "timestamps_sha256": hashlib.sha256(
            stamps.astype("int64").to_numpy().tobytes()
        ).hexdigest(),
        "first_open": str(stamps.iloc[0]),
        "last_open": str(stamps.iloc[-1]),
        "ohlc_valid": True,
    }


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    records, results = [], {}

    def fetch(key, name):
        record = {"url": BASE + key, "requested_at_ns": time.time_ns()}
        try:
            with requests.get(record["url"], timeout=20, stream=True) as response:
                record["status"] = response.status_code
                record["headers"] = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() in {"date", "last-modified", "etag", "content-type"}
                }
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > LIMIT:
                        raise ValueError("Response exceeds audit bound")
                    chunks.append(chunk)
                body = b"".join(chunks)
            (output / name).write_bytes(body)
            record.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            return body if record["status"] == 200 else None
        except (requests.RequestException, ValueError) as error:
            record["error"] = str(error)
            return None
        finally:
            record["received_at_ns"] = time.time_ns()
            records.append(record)

    for label, key in KEYS.items():
        body = fetch(key, label + ".zip")
        checksum = fetch(key + ".CHECKSUM", label + ".CHECKSUM")
        try:
            if body is None or checksum is None:
                raise ValueError("Archive or checksum unavailable")
            if hashlib.sha256(body).hexdigest() != checksum.decode().split()[0]:
                raise ValueError("Checksum mismatch")
            results[label] = {"sample_valid": True, "checksum_valid": True, **inspect(body)}
        except (ValueError, KeyError, IndexError) as error:
            results[label] = {"sample_valid": False, "error": str(error)}
    report = {
        "day": DAY,
        "contract": CONTRACT,
        "samples": results,
        "requests": len(records),
        "max_requests": 8,
        "four_series_aligned": all(r["sample_valid"] for r in results.values())
        and len({r.get("timestamps_sha256") for r in results.values()}) == 1,
        "coverage_beyond_sample_verified": False,
        "historical_margins_verified": False,
        "execution_model_verified": False,
        "historical_causal_backtest_ready": False,
        "returns_computed": False,
        "models_trained": 0,
        "backtests": 0,
        "validation_2024_read": False,
        "reserved_test_read": False,
    }
    (output / "requests.json").write_text(json.dumps(records, indent=2) + "\n")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "manifest.json").write_text(
        json.dumps(
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(output.iterdir())
                if p.is_file()
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    run(parser.parse_args().output)
