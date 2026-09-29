"""Read-only Binance derivatives coverage audit. No training, trading or DB writes."""

import argparse
import hashlib
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import numpy as np
import pandas as pd
import requests

BUCKET = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
BASE = "https://data.binance.vision/"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
LOCAL = threading.local()


def get(url, **kwargs):
    if not hasattr(LOCAL, "session"):
        LOCAL.session = requests.Session()
    for attempt in range(3):
        response = LOCAL.session.get(url, timeout=40, **kwargs)
        if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            time.sleep(2 ** (attempt + 1))
            continue
        response.raise_for_status()
        return response
    raise RuntimeError(url)


def inventory(prefix, output):
    marker, entries, page = "", [], 0
    while True:
        response = get(BUCKET, params={"prefix": prefix, "marker": marker, "max-keys": 1000})
        (output / f"listing-{page}.xml").write_bytes(response.content)
        root = ElementTree.fromstring(response.content)
        records = [
            {
                key: node.findtext(f"s:{key}", namespaces=NS)
                for key in ("Key", "Size", "LastModified")
            }
            for node in root.findall("s:Contents", NS)
        ]
        entries.extend(records)
        if not records or root.findtext("s:IsTruncated", namespaces=NS) == "false":
            break
        # Names sort chronologically: do not enumerate the reserved data years.
        if any("-2024" in r["Key"] or "-2025" in r["Key"] for r in records):
            break
        marker = records[-1]["Key"]
        page += 1
    return entries


def fetch_archive(record, folder):
    key = record["Key"]
    path = folder / Path(key).name
    checksum = path.with_suffix(".zip.CHECKSUM")
    if not path.exists():
        path.write_bytes(get(BASE + key).content)
    if not checksum.exists():
        checksum.write_bytes(get(BASE + key + ".CHECKSUM").content)
    parts = checksum.read_text().split()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if len(parts) != 2 or parts[0].lower() != digest or parts[1].lstrip("*") != path.name:
        raise ValueError(f"Checksum incorrecto: {path}")
    with ZipFile(path) as archive:
        if archive.namelist() != [path.with_suffix(".csv").name]:
            raise ValueError(f"CSV inesperado: {path}")
        frame = pd.read_csv(io.BytesIO(archive.read(archive.namelist()[0])))
    return frame, {**record, "sha256": digest, "rows": len(frame)}


def availability(index, events, tolerance):
    right = pd.DataFrame(
        {"assumed_available_at": events + pd.Timedelta(minutes=15), "present": True}
    )
    merged = pd.merge_asof(
        pd.DataFrame({"decision_at": index}),
        right,
        left_on="decision_at",
        right_on="assumed_available_at",
        direction="backward",
        allow_exact_matches=False,
        tolerance=pd.Timedelta(tolerance),
    )
    return pd.Series(merged.present.notna().to_numpy(), index=index)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {"cutoff_exclusive": "2024-01-01", "availability_is_assumption": True}
    frames = {}
    for kind, prefix in (
        ("funding", "data/futures/um/monthly/fundingRate/BTCUSDT/"),
        ("oi", "data/futures/um/daily/metrics/BTCUSDT/"),
    ):
        folder = args.output / kind
        folder.mkdir(exist_ok=True)
        entries = inventory(prefix, folder)
        selected = [
            r
            for r in entries
            if r["Key"].endswith(".zip")
            and "2020" <= Path(r["Key"]).name.split("-", 2)[2][:4] <= "2023"
        ]
        print(f"{kind}: {len(selected)} archives", flush=True)
        chunks, manifest = [], []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for n, (frame, record) in enumerate(
                pool.map(lambda r, folder=folder: fetch_archive(r, folder), selected), 1
            ):
                chunks.append(frame)
                manifest.append(record)
                if n % 100 == 0:
                    print(f"{kind}: {n}/{len(selected)} verified", flush=True)
        pd.DataFrame(manifest).to_csv(folder / "manifest.csv", index=False)
        frame = pd.concat(chunks, ignore_index=True)
        duplicates = int(frame.duplicated().sum())
        frame = frame.drop_duplicates()
        if kind == "funding":
            frame["time"] = pd.to_datetime(frame.calc_time, unit="ms", utc=True)
            values = ["last_funding_rate", "funding_interval_hours"]
            cadence = "8h"
        else:
            frame["time"] = pd.to_datetime(frame.create_time, utc=True)
            values = ["sum_open_interest", "sum_open_interest_value"]
            cadence = "5min"
            if not frame.symbol.eq("BTCUSDT").all():
                raise ValueError("Unexpected symbol")
        conflicts = frame.groupby("time")[values].nunique(dropna=False).max(axis=1).gt(1)
        conflict_times = conflicts.index[conflicts]
        valid = np.isfinite(frame[values].to_numpy()).all(axis=1)
        if kind == "oi":
            valid &= (frame[values] > 0).all(axis=1)
        invalid_rows = int((~valid).sum())
        frame = (
            frame.loc[valid & ~frame.time.isin(conflict_times)]
            .drop_duplicates("time")
            .sort_values("time")
        )
        frame.to_parquet(folder / "observations.parquet", index=False)
        events = pd.DatetimeIndex(frame.time)
        grid = pd.date_range("2020-01-01", "2024-01-01", freq=cadence, inclusive="left", tz="UTC")
        buckets = events.floor(cadence)
        missing = grid.difference(buckets)
        pd.Series(missing, name="missing_slot").to_csv(folder / "missing_slots.csv", index=False)
        gaps = pd.DataFrame({"previous": events[:-1], "next": events[1:]})
        gaps["seconds"] = (gaps.next - gaps.previous).dt.total_seconds()
        gaps = gaps[gaps.seconds > pd.Timedelta(cadence).total_seconds() + 1]
        gaps.to_csv(folder / "gaps.csv", index=False)
        summary[kind] = {
            "first": events.min().isoformat(),
            "last": events.max().isoformat(),
            "archives": len(manifest),
            "compressed_bytes": sum(int(m["Size"]) for m in manifest),
            "raw_rows": sum(m["rows"] for m in manifest),
            "exact_duplicates": duplicates,
            "conflicting_timestamps": len(conflict_times),
            "invalid_rows": invalid_rows,
            "valid_unique_observations": len(frame),
            "expected_slots_2020_2023": len(grid),
            "missing_slots_2020_2023": len(missing),
            "missing_slots_after_start": int((missing >= events.min().floor(cadence)).sum()),
            "gaps": len(gaps),
            "max_gap_seconds": float(gaps.seconds.max()) if len(gaps) else 0,
            "native_intervals": frame.funding_interval_hours.value_counts().to_dict()
            if kind == "funding"
            else None,
            "first_archive_last_modified": manifest[0]["LastModified"],
        }
        frames[kind] = events
    # Only train timestamps and split assignments are accessed, never outcomes or test rows.
    splits = pd.read_parquet(
        args.dataset / "splits.parquet",
        columns=["split"],
        filters=[("available_at", "<", pd.Timestamp("2024-01-01", tz="UTC"))],
    )
    index = splits.index[splits.split == "train"]
    available = pd.DataFrame(
        {
            kind: availability(index, events, "8h" if kind == "funding" else "15min")
            for kind, events in frames.items()
        },
        index=index,
    )
    available["both"] = available.funding & available.oi
    available.to_parquet(args.output / "availability_assumed.parquet")
    coverage = []
    boundaries = pd.to_datetime(
        ["2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01"], utc=True
    )
    for start, stop in zip(boundaries[:-1], boundaries[1:], strict=True):
        for part, mask in (
            ("train", index + pd.Timedelta(minutes=15) < start),
            ("eval", (index >= start) & (index + pd.Timedelta(minutes=15) < stop)),
        ):
            subset = available.loc[mask]
            coverage.append(
                {
                    "fold": start.isoformat(),
                    "partition": part,
                    "v1_rows": len(subset),
                    **{f"{kind}_rows": int(subset[kind].sum()) for kind in available},
                    **{f"{kind}_coverage": float(subset[kind].mean()) for kind in available},
                }
            )
    pd.DataFrame(coverage).to_csv(args.output / "fold_coverage.csv", index=False)
    calendar = pd.date_range("2020-01-01", "2023-07-01", freq="15min", inclusive="left", tz="UTC")
    summary["calendar_train_2020_to_2023H1"] = {
        kind: float(availability(calendar, events, "8h" if kind == "funding" else "15min").mean())
        for kind, events in frames.items()
    }
    summary["fold_coverage"] = coverage
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
