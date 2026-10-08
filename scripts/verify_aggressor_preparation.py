"""Verify frozen hashes, scalar formulas and paired indices without outcomes."""

import json
from pathlib import Path

import pandas as pd

from scripts.prepare_aggressor_flow import digest, independent_check
from scripts.prepare_sp500_experiment import FOLDS


def verify(output):
    manifest = json.loads((output / "final_manifest.json").read_text())
    for name, expected in manifest["files_sha256"].items():
        assert digest(output / name) == expected, name
    report = json.loads((output / "report.json").read_text())
    for path, expected in {**report["raw_sha256"], **report["source_index_sha256"]}.items():
        assert digest(Path(path)) == expected, path
    bars = pd.read_parquet(output / "flow_bars.parquet")
    count = 0
    for fold in FOLDS:
        for split in ("train", "evaluation"):
            folder = output / "alignment" / fold
            frame = pd.read_parquet(folder / f"{split}.parquet")
            independent_check(frame, bars)
            assert (frame.latest_source_open == frame.index - pd.Timedelta(minutes=30)).all()
            assert (frame.latest_source_close == frame.index - pd.Timedelta(minutes=15)).all()
            paired = pd.read_parquet(folder / f"{split}_paired_rows.parquet")
            pd.testing.assert_index_equal(
                paired.index, frame.index[frame.eligible_under_assumption]
            )
            count += len(frame)
    assert count == report["verified_rows"] == 450645
    return {"verified": True, "rows": count, "historical_availability_proven": False}
