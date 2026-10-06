"""Compare a small, fixed ALFRED vintage sample; never infer full PIT coverage."""

import argparse
import hashlib
import io
import json
from pathlib import Path

import pandas as pd

from scripts.audit_macro_sources import END, START, parse_snapshot

SAMPLES = [("SP500", "2023-01-10"), ("VIXCLS", "2023-01-10")]
SAMPLES += [("VIXCLS", f"{year}-12-31") for year in range(2019, 2024)]
SAMPLES += [("DTWEXBGS", "2023-01-10")]


def compare_vintage(raw, latest_raw, series, asof):
    frame = pd.read_csv(io.BytesIO(raw))
    expected = f"{series}_{asof.replace('-', '')}"
    if list(frame.columns) != ["observation_date", expected]:
        raise ValueError("Vintage header does not match requested series/date")
    frame.columns = ["observation_date", series]
    # Reuse duplicate, ordering, positivity and partition guards.
    historical = parse_snapshot(frame.to_csv(index=False).encode(), series).set_index(
        "observation_date"
    )
    if historical.index.max() > pd.Timestamp(asof):
        raise ValueError("Vintage contains observations after its as-of date")
    current = parse_snapshot(latest_raw, series).set_index("observation_date")
    pair = historical.join(current, lsuffix="_vintage", rsuffix="_current").dropna()
    if pair.empty:
        raise ValueError("No comparable observations")
    difference = (pair.value_vintage - pair.value_current).abs()
    return {
        "series": series,
        "requested_vintage": asof,
        "rows": len(historical),
        "nonmissing": int(historical.value.notna().sum()),
        "last_observation": str(historical.dropna().index.max().date()),
        "overlap": len(pair),
        "changed_values": int(difference.gt(1e-10).sum()),
        "max_abs_revision": float(difference.max()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "latest_sha256": hashlib.sha256(latest_raw).hexdigest(),
        "intraday_availability_proven": False,
    }


def audit(folder):
    records = []
    for series, asof in SAMPLES:
        path = folder / f"{series}_vintage_{asof.replace('-', '')}.csv"
        if not path.exists():
            records.append(
                {"series": series, "requested_vintage": asof, "status": "sample_unavailable"}
            )
            continue
        records.append(
            {
                "status": "validated_sample",
                **compare_vintage(
                    path.read_bytes(), (folder / f"{series}.csv").read_bytes(), series, asof
                ),
            }
        )
    sp = (
        parse_snapshot((folder / "SP500.csv").read_bytes(), "SP500")
        .set_index("observation_date")
        .value
    )
    vix = (
        parse_snapshot((folder / "VIXCLS.csv").read_bytes(), "VIXCLS")
        .set_index("observation_date")
        .value
    )
    extra = vix.loc[vix.notna() & sp.reindex(vix.index).isna()]
    calendar = pd.DataFrame(
        {"vix": extra, "previous_vix": vix.ffill().shift().reindex(extra.index)}
    )
    calendar.to_csv(folder / "vix_without_sp500.csv")
    result = {
        "window": [START, END],
        "samples": records,
        "vix_observations_without_sp500": len(extra),
        "vix_extra_values_different_from_previous": int(
            calendar.vix.ne(calendar.previous_vix).sum()
        ),
        "full_vintage_coverage_proven": False,
        "test_evaluated": False,
    }
    (folder / "vintage-comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    audit(args.folder)
