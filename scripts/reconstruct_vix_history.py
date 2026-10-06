"""Daily ALFRED VIX audit with resumable raw capture and explicitly assumed timing.

Run as a module. Never train, read BTC outcomes, or infer intraday availability.
"""

import argparse
import hashlib
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.audit_macro_sources import END, START, fetch_csv, parse_snapshot

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/experiments/iteration-13-20260930-four-hour"
POLICY = {
    "start": START,
    "end": END,
    "series": "VIXCLS",
    "assumed_vintage_delay_hours": 48,
    "max_observation_age_hours": 168,
    "max_vintage_age_hours": 24,
    "strict_asof": True,
    "intraday_availability_proven": False,
    "test_evaluated": False,
}


class FutureObservationsError(ValueError):
    def __init__(self, dates):
        super().__init__("Future observations in vintage")
        self.dates = dates


def parse_vintage(raw, day):
    frame = pd.read_csv(io.BytesIO(raw))
    expected = f"VIXCLS_{day.replace('-', '')}"
    if list(frame.columns) != ["observation_date", expected]:
        raise ValueError("Vintage identifier mismatch")
    frame.columns = ["observation_date", "VIXCLS"]
    frame = parse_snapshot(frame.to_csv(index=False).encode(), "VIXCLS")
    if frame.observation_date.max() > pd.Timestamp(day):
        raise FutureObservationsError(
            frame.loc[frame.observation_date.gt(pd.Timestamp(day)), "observation_date"]
            .dt.strftime("%Y-%m-%d")
            .tolist()
        )
    return frame.set_index("observation_date").value


def state_from_vintage(values, day):
    valid = values.dropna()
    observed = valid.index[-1].tz_localize("UTC")
    return {
        "vintage_date": pd.Timestamp(day, tz="UTC"),
        "assumed_available_at": pd.Timestamp(day, tz="UTC") + pd.Timedelta(hours=48),
        "observation_date": observed,
        "vix_level": float(valid.iloc[-1]),
        "vix_change_1_event": float(valid.iloc[-1] - valid.iloc[-2]) if len(valid) >= 2 else np.nan,
    }


def align_states(states, index):
    if index.tz is None or not index.is_monotonic_increasing or index.has_duplicates:
        raise ValueError("Decisions require sorted unique timezone-aware timestamps")
    if index.max() >= pd.Timestamp("2024-01-01", tz="UTC"):
        raise ValueError("No validation or test decisions allowed")
    if (
        states.assumed_available_at.duplicated().any()
        or not states.assumed_available_at.is_monotonic_increasing
    ):
        raise ValueError("States require sorted unique availability")
    result = pd.merge_asof(
        pd.DataFrame({"decision_at": index}),
        states,
        left_on="decision_at",
        right_on="assumed_available_at",
        allow_exact_matches=False,
        tolerance=pd.Timedelta(hours=24),
        direction="backward",
    )
    result["observation_date_age_hours"] = (
        result.decision_at - result.observation_date
    ).dt.total_seconds() / 3600
    result["vintage_age_hours"] = (
        result.decision_at - result.assumed_available_at
    ).dt.total_seconds() / 3600
    result["eligible_under_assumption"] = (
        result.vix_level.notna()
        & result.vix_change_1_event.notna()
        & result.observation_date_age_hours.between(0, 168)
    )
    return result.set_index("decision_at")


def capture(output, curl, workers=3, resume=False):
    if resume:
        assert json.loads((output / "policy.json").read_text()) == POLICY
    else:
        output.mkdir(parents=True, exist_ok=False)
        (output / "raw").mkdir()
        (output / "policy.json").write_text(json.dumps(POLICY, indent=2) + "\n")
    days = pd.date_range(START, END, freq="D").strftime("%Y-%m-%d").tolist()

    def one(day):
        raw_path, metadata_path = output / "raw" / f"{day}.csv", output / "raw" / f"{day}.json"
        if raw_path.exists() and metadata_path.exists():
            record = json.loads(metadata_path.read_text())
            if (
                record["status"] == "validated"
                and hashlib.sha256(raw_path.read_bytes()).hexdigest() == record["sha256"]
            ):
                parse_vintage(raw_path.read_bytes(), day)
                return record
            raise ValueError(f"Corrupt captured raw: {day}")
        url = f"https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=VIXCLS&cosd={START}&coed={END}&vintage_date={day}"
        record = {"vintage_date": day, "url": url, "attempted_at": datetime.now(UTC).isoformat()}
        try:
            time.sleep(0.2)
            raw = fetch_csv(url, "curl", curl)
            raw_path.write_bytes(raw)
            values = parse_vintage(raw, day)
            record.update(
                status="validated",
                sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw),
                rows=len(values),
                nonmissing=int(values.notna().sum()),
            )
        except Exception as error:
            record.update(status="failed", error=str(error))
            # Failures remain auditable and retryable without replacing validated raw.
            (output / f"failed-{day}.json").write_text(json.dumps(record, indent=2))
            return record
        metadata_path.write_text(json.dumps(record, indent=2) + "\n")
        return record

    records = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, day) for day in days]
        for future in as_completed(futures):
            records.append(future.result())
            if len(records) % 50 == 0 or len(records) == len(days):
                print(
                    f"Captured {len(records)}/{len(days)}; failed={sum(r['status'] != 'validated' for r in records)}",
                    flush=True,
                )
    records.sort(key=lambda r: r["vintage_date"])
    (output / "capture.json").write_text(json.dumps(records, indent=2) + "\n")
    if any(r["status"] != "validated" for r in records):
        raise ValueError("Incomplete capture: resume missing days before alignment")
    return records


def reconstruct(output, quarantine=False):
    assert json.loads((output / "policy.json").read_text()) == POLICY
    records = json.loads((output / "capture.json").read_text())
    expected = pd.date_range(START, END, freq="D").strftime("%Y-%m-%d").tolist()
    assert [r["vintage_date"] for r in records] == expected
    states, events, previous = [], [], None
    first_seen, quarantined = {}, []
    for record in records:
        day = record["vintage_date"]
        raw = (output / "raw" / f"{day}.csv").read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if "sha256" in record:
            assert digest == record["sha256"]
        try:
            values = parse_vintage(raw, day)
        except FutureObservationsError as error:
            if not quarantine:
                raise
            quarantined.append(
                {
                    "vintage_date": day,
                    "sha256": digest,
                    "future_observation_dates": error.dates,
                    "action": "exclude_entire_snapshot",
                }
            )
            continue
        assert record["status"] == "validated"
        states.append(state_from_vintage(values, day))
        for observed in values.dropna().index:
            first_seen.setdefault(str(observed.date()), day)
        if previous is not None:
            combined = pd.concat([previous.rename("old"), values.rename("new")], axis=1)
            changed = (
                combined.old.notna()
                & combined.new.notna()
                & (combined.old - combined.new).abs().gt(1e-10)
            )
            removed = combined.old.notna() & combined.new.isna()
            for kind, mask in (("revision", changed), ("withdrawal", removed)):
                for observed, row in combined.loc[mask].iterrows():
                    events.append(
                        {
                            "vintage_date": day,
                            "observation_date": str(observed.date()),
                            "kind": kind,
                            "old": row.old,
                            "new": row.new,
                        }
                    )
        previous = values
    states = pd.DataFrame(states)
    (output / "quarantine.json").write_text(json.dumps(quarantined, indent=2) + "\n")
    states.to_parquet(output / "daily_states.parquet", index=False)
    pd.DataFrame(events, columns=["vintage_date", "observation_date", "kind", "old", "new"]).to_csv(
        output / "revision_events.csv", index=False
    )
    pd.DataFrame(
        [{"observation_date": o, "first_seen_vintage_date": d} for o, d in first_seen.items()]
    ).to_csv(output / "first_seen.csv", index=False)
    coverage, hashes = [], {}
    for fold in ("2022 H1", "2022 H2", "2023 H1", "2023 H2"):
        for split, path in (
            ("train", SOURCE / "folds" / fold / "train_rows.parquet"),
            ("evaluation", SOURCE / "seed_42" / fold / "four_hour/predictions.parquet"),
        ):
            hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
            # Index only. No prices, outcomes, probabilities or strategy metrics read.
            index = pd.read_parquet(path, columns=[]).index
            aligned = align_states(states, index)
            folder = output / "alignment" / fold
            folder.mkdir(parents=True, exist_ok=True)
            aligned.to_parquet(folder / f"{split}.parquet")
            eligible = aligned.eligible_under_assumption
            coverage.append(
                {
                    "fold": fold,
                    "split": split,
                    "rows": len(index),
                    "eligible": int(eligible.sum()),
                    "coverage_under_assumption": float(eligible.mean()),
                    "max_observation_date_age_hours": float(
                        aligned.observation_date_age_hours.max()
                    ),
                    "first_eligible": str(aligned.index[eligible][0]) if eligible.any() else None,
                }
            )
    pd.DataFrame(coverage).to_csv(output / "coverage.csv", index=False)
    first_seen_lags = [(pd.Timestamp(d) - pd.Timestamp(o)).days for o, d in first_seen.items()]
    result = {
        "captured_vintages": len(records),
        "quarantined_vintages": len(quarantined),
        "quarantine_mode": "whole_snapshot" if quarantine else "none",
        "vintages": len(states),
        "observation_dates": len(first_seen),
        "revision_events": len(events),
        "max_first_seen_lag_days": max(first_seen_lags),
        "coverage": coverage,
        "assumed_timing": POLICY,
        "ready_for_training": False,
        "models_trained": 0,
        "backtests_run": 0,
        "test_evaluated": False,
        "index_source_sha256": hashes,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (output / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--curl-executable", default="curl")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--quarantine",
        action="store_true",
        help="Offline diagnostic only: exclude whole snapshots with future observations",
    )
    args = parser.parse_args()
    if args.quarantine and not args.offline:
        parser.error("Quarantine diagnosis requires --offline; capture validation remains strict")
    if not args.offline:
        capture(args.output, args.curl_executable, resume=args.resume)
    reconstruct(args.output, quarantine=args.quarantine)
