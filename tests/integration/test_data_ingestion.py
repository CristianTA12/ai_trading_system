"""Opt-in database test in a unique disposable schema, never in public.ohlcv."""

import os
import uuid

import psycopg2
import pytest
from psycopg2 import sql
from psycopg2.extensions import make_dsn

from src.config.settings import settings
from src.data.downloaders import historical_downloader as downloader


@pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 with TimescaleDB running"
)
def test_repeat_load_and_transaction_rollback(make_archive, monkeypatch):
    _, root = make_archive()
    schema = "test_ingestion_" + uuid.uuid4().hex
    connection = psycopg2.connect(settings.database.url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            cursor.execute(
                sql.SQL("CREATE TABLE {}.ohlcv (LIKE public.ohlcv INCLUDING ALL)").format(
                    sql.Identifier(schema)
                )
            )
        monkeypatch.setattr(
            settings.database,
            "url",
            make_dsn(settings.database.url, options=f"-c search_path={schema},public"),
        )
        assert downloader.load_month("2024-02", root)["written_rows"] == 41760
        assert downloader.load_month("2024-02", root)["written_rows"] == 0
        make_archive(omit_last=True)
        partial = downloader.load_month("2024-02", root, allow_gaps=True)
        assert partial["accepted_with_gaps"]
        assert partial["written_rows"] == 0
        assert partial["removed_rows"] == 1
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("SELECT count(*) FROM {}.ohlcv").format(sql.Identifier(schema)))
            assert cursor.fetchone()[0] == 41759
        make_archive(close=106)
        assert downloader.load_month("2024-02", root)["written_rows"] == 41760
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT count(*), min(close), max(close) FROM {}.ohlcv").format(
                    sql.Identifier(schema)
                )
            )
            assert cursor.fetchone() == (41760, 106, 106)
            cursor.execute(sql.SQL("TRUNCATE {}.ohlcv").format(sql.Identifier(schema)))
        original = downloader.execute_values
        calls = 0

        def fail_second_batch(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated failure")
            return original(*args, **kwargs)

        monkeypatch.setattr(downloader, "execute_values", fail_second_batch)
        with pytest.raises(RuntimeError, match="simulated"):
            downloader.load_month("2024-02", root)
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("SELECT count(*) FROM {}.ohlcv").format(sql.Identifier(schema)))
            assert cursor.fetchone()[0] == 0
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
            )
        connection.close()
