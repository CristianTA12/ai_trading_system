"""Verify immutable feature artifacts and expose only train / validation to experiments."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtesting.engine import STEP, validate_index


@dataclass
class ExperimentData:
    metadata: dict
    train_features: pd.DataFrame
    train_returns: pd.Series
    validation_features: pd.DataFrame
    validation_returns: pd.Series
    validation_bars: pd.DataFrame
    benchmark_features: pd.DataFrame
    train_bars: pd.DataFrame | None = None


def load_dataset(path: Path) -> ExperimentData:
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    frames = {}
    for name in ("bars", "features", "labels", "splits"):
        filename = f"{name}.parquet"
        with (path / filename).open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != metadata["sha256"][filename]:
            raise ValueError(f"Checksum incorrecto: {filename}")
        frames[name] = pd.read_parquet(path / filename)
        validate_index(frames[name].index)
    bars, features, labels, splits = (
        frames[name] for name in ("bars", "features", "labels", "splits")
    )
    if metadata["timeframe"] != "15m" or metadata["exchange"] != "binance_spot":
        raise ValueError("Este experimento requiere Binance spot de 15 minutos")
    if list(features.columns) != metadata["feature_columns"]:
        raise ValueError("Orden o columnas de features diferentes del contrato")
    if set(features.columns) & set(labels.columns):
        raise ValueError("Los objetivos no pueden ser predictores")
    if not np.isfinite(features.to_numpy()).all() or not labels.index.equals(splits.index):
        raise ValueError("Features no finitas o labels/splits desalineados")
    if not labels.index.isin(features.index).all():
        raise ValueError("Existen labels sin features")
    start = pd.Timestamp(metadata["train_end"], tz="UTC")
    stop = pd.Timestamp(metadata["validation_end"], tz="UTC")
    if start >= stop or not splits.split.isin(["train", "validation", "test", "purged"]).all():
        raise ValueError("Particiones inválidas")
    subsets = {}
    for name, lower, upper in (("train", None, start), ("validation", start, stop)):
        index = splits.index[splits.split == name]
        outcomes = labels.loc[index]
        if (
            index.empty
            or (index >= upper).any()
            or (lower is not None and (index < lower).any())
            or (outcomes.label_end >= upper).any()
            or not (outcomes.label_end == index + STEP).all()
            or not np.isfinite(outcomes.target_return_next_15m).all()
        ):
            raise ValueError(f"Partición {name} vacía o con fuga temporal")
        if not index.isin(bars.index).all():
            raise ValueError("Faltan velas de ejecución")
        realized = bars.loc[index, "close"] / bars.loc[index, "open"] - 1
        if not np.allclose(realized, outcomes.target_return_next_15m, rtol=1e-10, atol=1e-12):
            raise ValueError("Labels no corresponden a las velas de ejecución")
        subsets[name] = (features.loc[index], outcomes.target_return_next_15m)
    return ExperimentData(
        metadata,
        *subsets["train"],
        *subsets["validation"],
        bars.loc[(bars.index >= start) & (bars.index < stop)],
        features.loc[(features.index >= start) & (features.index < stop)],
        bars.loc[bars.index < start],
    )
