"""Synthetic monthly archives; tests do not download market data."""

import hashlib
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from src.data.downloaders.historical_downloader import archive_path
from src.data.validators.data_quality_validator import month_bounds


@pytest.fixture
def make_archive(tmp_path):
    def create(month="2024-02", omit_last=False, close=105):
        start, end = month_bounds(month)
        times = pd.date_range(start, end, freq="min", inclusive="left")
        if omit_last:
            times = times[:-1]
        multiplier = 1_000_000 if month >= "2025-01" else 1000
        lines = []
        for stamp in times:
            opening = int(stamp.timestamp()) * multiplier
            closing = opening + 60 * multiplier - 1
            lines.append(f"{opening},100,110,90,{close},2,{closing},200,3,1,100,0\n")
        path = archive_path(month, tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(path, "w", ZIP_DEFLATED) as archive:
            archive.writestr(path.with_suffix(".csv").name, "".join(lines))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(".zip.CHECKSUM").write_text(f"{digest}  {path.name}\n")
        return path, tmp_path

    return create
