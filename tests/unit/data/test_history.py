import hashlib
import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from src.data.downloaders import history
from src.data.downloaders.historical_downloader import read_archive, validate_archive


def test_month_range_year_boundary():
    assert history.month_range("2023-11", "2024-02") == ["2023-11", "2023-12", "2024-01", "2024-02"]
    with pytest.raises(ValueError):
        history.month_range("2024-02", "2023-11")


def test_failure_is_recorded_and_other_months_continue(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "download_archive", lambda *args: None)

    def load(month, *args, **kwargs):
        if month == "2024-02":
            raise ValueError("bad month")
        return {"month": month, "rows": 10, "missing_minutes": 0, "written_rows": 10}

    monkeypatch.setattr(history, "load_month", load)
    path = tmp_path / "report.json"
    result = history.sync_history("2024-01", "2024-03", report_path=path)
    assert not result["complete"]
    assert [row["status"] for row in result["months"]] == ["loaded", "failed", "loaded"]
    assert json.loads(path.read_text()) == result


@pytest.mark.parametrize("duration,can_quarantine", [(30000, True), (-1, False), (60000, False)])
def test_truncated_candle_policy(make_archive, duration, can_quarantine):
    path, root = make_archive()
    with ZipFile(path) as archive:
        rows = archive.read(path.with_suffix(".csv").name).decode().splitlines()
    fields = rows[10].split(",")
    fields[6] = str(int(fields[0]) + duration)
    rows[10] = ",".join(fields)
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(path.with_suffix(".csv").name, "\n".join(rows) + "\n")
    path.with_suffix(".zip.CHECKSUM").write_text(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name
    )
    with pytest.raises(ValueError, match="Duración"):
        read_archive(path, "2024-02")
    if can_quarantine:
        _, report = validate_archive("2024-02", root, exclude_truncated=True)
        assert report["excluded_truncated_rows"] == 1
        assert report["missing_minutes"] == 1
        assert report["quarantine"][0]["csv_row"] == 11
        assert not report["valid"]
    else:
        with pytest.raises(ValueError, match="Duración"):
            read_archive(path, "2024-02", exclude_truncated=True)
