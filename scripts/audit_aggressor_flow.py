"""Read-only 2020-2023 aggressor-flow audit; no models or performance evaluation."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from src.backtesting.dataset import load_dataset
from src.data.downloaders.historical_downloader import COLUMNS, verify_checksum
from src.training.four_hour_experiment import DATASET

OUT = Path("data/external/aggressor-flow-audit-20261008-complete")
RAW = Path("data/raw/binance/spot/BTCUSDT/1m")
CURL = "/mnt/c/Windows/System32/curl.exe"
MONTHS = [f"{year}-{month:02d}" for year in range(2020, 2024) for month in range(1, 13)]
DAYS = ("2020-01-01", "2023-01-01")


def fetch(url, path, head=False):
    windows_path = subprocess.check_output(
        ["wslpath", "-w", str(path.resolve())], text=True
    ).strip()
    args = [
        CURL,
        "--silent",
        "--show-error",
        "--fail",
        "--connect-timeout",
        "15",
        "--max-time",
        "120",
    ]
    if head:
        args += ["--head"]
    else:
        args += ["--max-filesize", "75000000"]
    completed = subprocess.run(
        args + [url, "--output", windows_path], capture_output=True, text=True
    )
    return {
        "url": url,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "error": completed.stderr[-400:] if completed.returncode else None,
    }


def inspect_month(month):
    path = RAW / f"BTCUSDT-1m-{month}.zip"
    digest = verify_checksum(path)
    with ZipFile(path) as archive:
        assert archive.namelist() == [path.with_suffix(".csv").name]
        with archive.open(archive.namelist()[0]) as stream:
            frame = pd.read_csv(stream, header=None, names=COLUMNS)
    assert frame.shape[1] == 12
    time = pd.to_datetime(frame.timestamp, unit="ms", utc=True)
    assert time.is_monotonic_increasing and not time.duplicated().any()
    assert time.dt.strftime("%Y-%m").eq(month).all()
    assert time.eq(time.dt.floor("min")).all()
    fields = ["volume", "quote_volume", "taker_base", "taker_quote"]
    values = frame[fields].to_numpy(dtype=float)
    valid = np.isfinite(values).all(axis=1) & (values >= 0).all(axis=1)
    valid &= (frame.taker_base <= frame.volume + 1e-8) & (
        frame.taker_quote <= frame.quote_volume + 1e-8
    )
    duration = frame.close_time - frame.timestamp == 59999
    report = {
        "month": month,
        "sha256": digest,
        "zip_bytes": path.stat().st_size,
        "rows": len(frame),
        "flow_invalid_rows": int((~valid).sum()),
        "invalid_duration_rows": int((~duration).sum()),
        "zero_volume_rows": int(frame.volume.eq(0).sum()),
        "missing_minutes": int(
            (
                pd.Timestamp(month, tz="UTC")
                + pd.offsets.MonthBegin(1)
                - pd.Timestamp(month, tz="UTC")
            ).total_seconds()
            / 60
            - len(frame)
        ),
    }
    frame.index = pd.DatetimeIndex(time, name="time")
    return report, frame.loc[
        (valid & duration).to_numpy(),
        ["volume", "quote_volume", "taker_base", "taker_quote", "trades"],
    ]


def remote_month(month):
    path = OUT / f"aggTrades-{month}.headers.txt"
    record = fetch(
        f"https://data.binance.vision/data/spot/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{month}.zip",
        path,
        head=True,
    )
    record["month"] = month
    if record["ok"]:
        sizes = [
            line.split(":", 1)[1].strip()
            for line in path.read_text().splitlines()
            if line.lower().startswith("content-length:")
        ]
        record["compressed_bytes"] = int(sizes[-1]) if sizes else None
    return record


def crosscheck(day, minutes):
    path = OUT / f"BTCUSDT-aggTrades-{day}.zip"
    url = f"https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/{path.name}"
    for suffix in (".CHECKSUM", ""):
        report = fetch(url + suffix, Path(str(path) + suffix))
        if not report["ok"]:
            return {"day": day, "download": report, "verified": False}
    digest = verify_checksum(path)
    with ZipFile(path) as archive:
        assert archive.namelist() == [path.with_suffix(".csv").name]
        assert archive.infolist()[0].file_size < 750000000
        with archive.open(archive.namelist()[0]) as stream:
            trades = pd.read_csv(
                stream,
                header=None,
                names=["id", "price", "qty", "first", "last", "time", "buyer_maker", "best"],
            )
    assert trades.buyer_maker.isin([True, False]).all()
    assert np.isfinite(trades[["price", "qty"]].to_numpy()).all()
    assert (trades[["price", "qty"]] > 0).all().all()
    assert (trades["last"] >= trades["first"]).all()
    times = pd.to_datetime(trades.time, unit="ms", utc=True)
    assert times.dt.strftime("%Y-%m-%d").eq(day).all() and times.is_monotonic_increasing
    assert trades.id.is_monotonic_increasing and not trades.id.duplicated().any()
    trades["minute"] = times.dt.floor("min")
    trades["volume"] = trades.qty
    trades["quote_volume"] = trades.qty * trades.price
    trades["taker_base"] = trades.qty.where(~trades.buyer_maker, 0)
    trades["taker_quote"] = trades.quote_volume.where(~trades.buyer_maker, 0)
    fields = ["volume", "quote_volume", "taker_base", "taker_quote"]
    grouped = trades.groupby("minute")[fields].sum()
    expected = minutes.loc[day, fields]
    common = grouped.index.intersection(expected.index)
    compared = {
        field: {
            "max_abs_difference": float(
                (grouped.loc[common, field] - expected.loc[common, field]).abs().max()
            ),
            "matching_minutes": int(
                np.isclose(
                    grouped.loc[common, field], expected.loc[common, field], rtol=1e-9, atol=1e-6
                ).sum()
            ),
        }
        for field in fields
    }
    return {
        "day": day,
        "sha256": digest,
        "rows": len(trades),
        "zip_bytes": path.stat().st_size,
        "csv_bytes": archive.infolist()[0].file_size,
        "missing_aggregate_ids": int((trades.id.diff().dropna() != 1).sum()),
        "common_minutes": len(common),
        "kline_minutes": len(expected),
        "aggregate_minutes": len(grouped),
        "comparison": compared,
        "verified": len(common) == len(expected) == len(grouped)
        and all(x["matching_minutes"] == len(common) for x in compared.values()),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    reports = []
    frames = []
    for month in MONTHS:
        report, frame = inspect_month(month)
        reports.append(report)
        frames.append(frame)
    minutes = pd.concat(frames)
    monthly = pd.DataFrame(reports)
    monthly.to_csv(OUT / "local_months.csv", index=False)
    grouped = minutes.resample("15min", closed="left", label="left").agg(
        volume=("volume", "sum"),
        trades=("trades", "sum"),
        taker_base=("taker_base", "sum"),
        quote_volume=("quote_volume", "sum"),
        taker_quote=("taker_quote", "sum"),
        source_minutes=("volume", "size"),
    )
    flow = grouped.loc[grouped.source_minutes == 15].copy()
    data = load_dataset(DATASET, train_only=True)
    reference = data.train_bars
    common = reference.index.intersection(flow.index)
    assert np.allclose(
        reference.loc[common, "volume"], flow.loc[common, "volume"], rtol=1e-10, atol=1e-8
    )
    assert np.array_equal(reference.loc[common, "trades"], flow.loc[common, "trades"])
    # Coverage for a strict '<' join on close times: last eligible whole 15m bar.
    eligible = flow.index + pd.Timedelta(minutes=30)
    coverage = []
    for start, stop in zip(
        ["2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01"],
        ["2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01"],
        strict=True,
    ):
        index = reference.index[(reference.index >= start) & (reference.index < stop)]
        coverage.append(
            {
                "fold_start": start,
                "bars": len(index),
                "strict_lag_covered": int(index.isin(eligible).sum()),
                "fraction": float(index.isin(eligible).mean()),
            }
        )
    print("Local raw audit complete", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        remote = list(pool.map(remote_month, MONTHS))
    (OUT / "remote_inventory.json").write_text(json.dumps(remote, indent=2) + "\n")
    print("Remote HEAD inventory complete", flush=True)
    samples = [crosscheck(day, minutes) for day in DAYS]
    summary = {
        "months": len(reports),
        "raw_rows": int(monthly.rows.sum()),
        "raw_zip_bytes": int(monthly.zip_bytes.sum()),
        "flow_invalid_rows": int(monthly.flow_invalid_rows.sum()),
        "invalid_duration_rows": int(monthly.invalid_duration_rows.sum()),
        "missing_minutes": int(monthly.missing_minutes.sum()),
        "zero_volume_rows": int(monthly.zero_volume_rows.sum()),
        "complete_flow_bars": len(flow),
        "reference_bars": len(reference),
        "matched_reference_bars": len(common),
        "causal_lag_coverage": coverage,
        "remote_months_available": sum(row["ok"] for row in remote),
        "remote_total_compressed_bytes_known": sum(
            row.get("compressed_bytes") or 0 for row in remote
        ),
        "remote_months_size_known": sum(row.get("compressed_bytes") is not None for row in remote),
        "samples": samples,
        "test_evaluated": False,
        "models_trained": 0,
        "backtests": 0,
        "historical_receive_latency_proven": False,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
