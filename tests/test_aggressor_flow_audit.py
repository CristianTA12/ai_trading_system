import hashlib
from zipfile import ZipFile

from scripts import audit_aggressor_flow as audit


def test_raw_audit_preserves_flow_and_quarantines_invalid_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "RAW", tmp_path)
    path = tmp_path / "BTCUSDT-1m-2020-01.zip"
    rows = []
    for i, (buy, duration) in enumerate([(3, 59999), (11, 59999), (2, 59998)]):
        timestamp = 1577836800000 + i * 60000
        rows.append(
            f"{timestamp},100,100,100,100,10,{timestamp + duration},1000,2,{buy},{buy * 100},0"
        )
    with ZipFile(path, "w") as archive:
        archive.writestr(path.with_suffix(".csv").name, "\n".join(rows) + "\n")
    path.with_suffix(".zip.CHECKSUM").write_text(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name
    )
    report, frame = audit.inspect_month("2020-01")
    assert report["flow_invalid_rows"] == 1
    assert report["invalid_duration_rows"] == 1
    assert len(frame) == 1
    assert frame.iloc[0].taker_base == 3
    assert str(frame.index.tz) == "UTC"


def test_sample_days_and_inventory_exclude_holdout():
    assert len(audit.MONTHS) == 48
    assert max(audit.MONTHS) == "2023-12"
    assert all(day < "2024-01-01" for day in audit.DAYS)
