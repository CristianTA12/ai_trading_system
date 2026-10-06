"""Independent raw/state and searchsorted alignment verification of the VIX audit."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def verify(folder):
    report = json.loads((folder / "report.json").read_text())
    records = json.loads((folder / "capture.json").read_text())
    states = pd.read_parquet(folder / "daily_states.parquet")
    quarantined = {
        r["vintage_date"]: r for r in json.loads((folder / "quarantine.json").read_text())
    }
    dates = pd.date_range("2019-11-01", "2023-12-31", freq="D", tz="UTC")
    assert len(records) == len(dates) == 1522
    assert len(states) + len(quarantined) == 1522
    assert report["quarantined_vintages"] == len(quarantined)
    accepted_dates = dates[~dates.strftime("%Y-%m-%d").isin(quarantined)]
    np.testing.assert_array_equal(states.vintage_date, accepted_dates)
    np.testing.assert_array_equal(
        states.assumed_available_at, accepted_dates + pd.Timedelta(hours=48)
    )
    number = 0
    for capture_number, record in enumerate(records):
        day = record["vintage_date"]
        assert day == dates[capture_number].strftime("%Y-%m-%d")
        raw_path = folder / "raw" / f"{day}.csv"
        digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        raw = pd.read_csv(raw_path, index_col=0)
        assert raw.columns.tolist() == ["VIXCLS_" + day.replace("-", "")]
        assert raw.index.is_unique and raw.index.is_monotonic_increasing
        assert (pd.to_datetime(raw.index) >= pd.Timestamp("2019-11-01")).all()
        assert (pd.to_datetime(raw.index) <= pd.Timestamp("2023-12-31")).all()
        values = raw.iloc[:, 0].dropna()
        assert np.isfinite(values).all() and values.gt(0).all()
        future = raw.index[pd.to_datetime(raw.index) > pd.Timestamp(day)].tolist()
        if day in quarantined:
            assert future == quarantined[day]["future_observation_dates"] and future
            assert digest == quarantined[day]["sha256"]
            continue
        assert not future and record["status"] == "validated"
        assert digest == record["sha256"]
        assert states.iloc[number].vix_level == values.iloc[-1]
        assert states.iloc[number].observation_date == pd.Timestamp(values.index[-1], tz="UTC")
        expected_change = values.iloc[-1] - values.iloc[-2] if len(values) > 1 else np.nan
        np.testing.assert_equal(states.iloc[number].vix_change_1_event, expected_change)
        number += 1
    available = pd.DatetimeIndex(states.assumed_available_at).as_unit("ns").asi8
    ns_hour = pd.Timedelta(hours=1).value
    verified_rows = 0
    for path in sorted((folder / "alignment").glob("*/*.parquet")):
        actual = pd.read_parquet(path)
        index = actual.index
        assert index.max() < pd.Timestamp("2024-01-01", tz="UTC")
        decision_ns = index.as_unit("ns").asi8
        positions = np.searchsorted(available, decision_ns, side="left") - 1
        assert (positions >= 0).all()
        selected = states.iloc[positions]
        vintage_age = (decision_ns - available[positions]) / ns_hour
        observation_age = (
            decision_ns - pd.DatetimeIndex(selected.observation_date).as_unit("ns").asi8
        ) / ns_hour
        known = (vintage_age > 0) & (vintage_age <= 24)
        eligible = (
            known
            & (observation_age >= 0)
            & (observation_age <= 168)
            & selected.vix_change_1_event.notna().to_numpy()
        )
        np.testing.assert_array_equal(actual.eligible_under_assumption, eligible)
        for column in ("vix_level", "vix_change_1_event"):
            np.testing.assert_array_equal(actual[column], np.where(known, selected[column], np.nan))
        np.testing.assert_array_equal(
            actual.observation_date_age_hours, np.where(known, observation_age, np.nan)
        )
        np.testing.assert_array_equal(
            actual.vintage_age_hours, np.where(known, vintage_age, np.nan)
        )
        row = next(
            r
            for r in report["coverage"]
            if r["fold"] == path.parent.name and r["split"] == path.stem
        )
        assert row["eligible"] == int(eligible.sum()) and row["rows"] == len(index)
        verified_rows += len(index)
    root = Path(__file__).resolve().parents[1]
    for name, digest in report["index_source_sha256"].items():
        path = root / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        source_index = pd.read_parquet(path, columns=[]).index
        fold = path.parent.name if path.name == "train_rows.parquet" else path.parent.parent.name
        split = "train" if path.name == "train_rows.parquet" else "evaluation"
        aligned = pd.read_parquet(folder / "alignment" / fold / f"{split}.parquet", columns=[])
        pd.testing.assert_index_equal(source_index, aligned.index, check_names=False)
    return {
        "verified": True,
        "raw_vintages": len(records),
        "accepted_vintages": len(states),
        "quarantined_vintages": len(quarantined),
        "alignment_rows": verified_rows,
        "independent_searchsorted_join": True,
        "exact_original_indices": True,
        "intraday_availability_proven": False,
        "models_trained": 0,
        "test_evaluated": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder), indent=2))
