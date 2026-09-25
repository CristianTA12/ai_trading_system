from datetime import UTC, datetime
from unittest.mock import Mock
from urllib.error import HTTPError

import pandas as pd
import pytest
from click.testing import CliRunner

from src.cli import main
from src.data.downloaders import historical_downloader as downloader
from src.data.validators.data_quality_validator import month_bounds, validate_candles


@pytest.mark.parametrize("month,rows", [("2024-02", 41760), ("2025-01", 44640)])
def test_timestamp_units_and_complete_month(make_archive, month, rows):
    _, root = make_archive(month)
    frame, report = downloader.validate_archive(month, root)
    assert report["valid"]
    assert report["rows"] == rows
    assert frame.iloc[0].time == pd.Timestamp(f"{month}-01", tz="UTC")


@pytest.mark.parametrize("month", ["2024-2", "2024-13", "../2024-01", "2999-01"])
def test_bad_or_unfinished_month(month):
    with pytest.raises(ValueError):
        month_bounds(month)


def test_current_month_rejected():
    with pytest.raises(ValueError, match="mes completo"):
        month_bounds(datetime.now(UTC).strftime("%Y-%m"))


def test_missing_boundary_blocks_database(make_archive, monkeypatch):
    _, root = make_archive(omit_last=True)
    connect = Mock()
    monkeypatch.setattr(downloader.psycopg2, "connect", connect)
    _, report = downloader.validate_archive("2024-02", root)
    assert report["missing_minutes"] == 1
    with pytest.raises(ValueError, match="Validación rechazada"):
        downloader.load_month("2024-02", root)
    connect.assert_not_called()


def test_duplicate_does_not_mask_gap(make_archive):
    path, _ = make_archive()
    frame = downloader.read_archive(path, "2024-02")
    frame.loc[1, "time"] = frame.loc[0, "time"]
    report = validate_candles(frame, "2024-02")
    assert report["duplicate_rows"] == 1
    assert report["missing_minutes"] == 1
    assert not report["valid"]


@pytest.mark.parametrize(
    "column,value",
    [
        ("high", 95),
        ("low", 106),
        ("volume", -1),
        ("open", float("nan")),
        ("close", float("inf")),
        ("trades", 1.5),
    ],
)
def test_bad_prices_and_activity(make_archive, column, value):
    path, _ = make_archive()
    frame = downloader.read_archive(path, "2024-02").astype({column: float})
    frame.loc[5, column] = value
    report = validate_candles(frame, "2024-02")
    assert report["invalid_rows"] == 1
    assert not report["valid"]


def test_unsorted_and_out_of_range_rejected(make_archive):
    path, _ = make_archive()
    frame = downloader.read_archive(path, "2024-02")
    assert not validate_candles(frame.iloc[::-1], "2024-02")["valid"]
    frame.loc[0, "time"] -= pd.Timedelta(minutes=1)
    assert validate_candles(frame, "2024-02")["invalid_rows"] == 1


def test_checksum_rejects_corruption(make_archive):
    path, _ = make_archive()
    with path.open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(ValueError, match="Checksum"):
        downloader.verify_checksum(path)


def test_cache_and_validation_work_offline(make_archive, monkeypatch):
    path, root = make_archive()
    monkeypatch.setattr(downloader, "urlopen", Mock(side_effect=AssertionError("Network")))
    assert downloader.download_archive("2024-02", root) == path
    result = CliRunner().invoke(
        main, ["validate-data", "--month", "2024-02", "--raw-dir", str(root)]
    )
    assert result.exit_code == 0, result.output
    assert '"valid": true' in result.output


def test_failed_refresh_preserves_valid_cache(make_archive, monkeypatch):
    path, root = make_archive()
    before = path.read_bytes()
    monkeypatch.setattr(
        downloader, "urlopen", Mock(side_effect=HTTPError("url", 404, "missing", {}, None))
    )
    with pytest.raises(ValueError, match="publicado"):
        downloader.download_archive("2024-02", root, refresh=True)
    assert path.read_bytes() == before
    downloader.verify_checksum(path)


def test_invalid_cli_exit_status(tmp_path):
    result = CliRunner().invoke(
        main, ["validate-data", "--month", "2024-02", "--raw-dir", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "Falta el ZIP" in result.output
