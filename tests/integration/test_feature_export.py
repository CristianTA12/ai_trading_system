"""Real PostgreSQL aggregation and Parquet export in an isolated schema."""

import json
import os
import uuid

import pandas as pd
import psycopg2
import pytest
from psycopg2 import sql
from psycopg2.extensions import make_dsn
from psycopg2.extras import execute_values

from src.config.settings import settings
from src.features.dataset import aggregate_minutes, build_features, export_dataset


@pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires local PostgreSQL")
def test_database_export_matches_causal_pipeline(tmp_path, monkeypatch):
    schema = "test_features_" + uuid.uuid4().hex
    connection = psycopg2.connect(settings.database.url)
    connection.autocommit = True
    frames = []
    for month in ("2023-12", "2024-01", "2024-02"):
        index = pd.date_range(month + "-01", periods=1800, freq="min", tz="UTC")
        frame = pd.DataFrame(
            {
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 5.0,
                "trades": 10,
            },
            index=index,
        )
        frames.append(frame)
    minutes = pd.concat(frames).drop(frames[1].index[900])
    rows = [
        (stamp.to_pydatetime(), "BTC/USDT", "binance_spot", "1m", *row)
        for stamp, row in zip(minutes.index, minutes.itertuples(index=False), strict=True)
    ]
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            cursor.execute(
                sql.SQL("CREATE TABLE {}.ohlcv (LIKE public.ohlcv INCLUDING ALL)").format(
                    sql.Identifier(schema)
                )
            )
            execute_values(
                cursor,
                sql.SQL(
                    "INSERT INTO {}.ohlcv (time,symbol,exchange,timeframe,open,high,low,close,volume,trades) VALUES %s"
                ).format(sql.Identifier(schema)),
                rows,
            )
        monkeypatch.setattr(
            settings.database,
            "url",
            make_dsn(settings.database.url, options=f"-c search_path={schema},public"),
        )
        output = tmp_path / "dataset"
        metadata = export_dataset("2023-12", "2024-02", output, "2024-01-01", "2024-02-01")
        expected = build_features(aggregate_minutes(minutes))
        actual = pd.read_parquet(output / "features.parquet")
        pd.testing.assert_frame_equal(actual, expected)
        assert metadata["source_minutes"] == 5399
        assert metadata["complete_bars"] == 359
        assert set(metadata["split_rows"]) == {"train", "validation", "test"}
        assert json.loads((output / "metadata.json").read_text())["sha256"] == metadata["sha256"]
        with pytest.raises(ValueError, match="ya existe"):
            export_dataset("2023-12", "2024-02", output, "2024-01-01", "2024-02-01")
        with pytest.raises(ValueError, match="Faltan meses"):
            export_dataset("2023-11", "2024-02", tmp_path / "absent", "2024-01-01", "2024-02-01")
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
            )
        connection.close()
