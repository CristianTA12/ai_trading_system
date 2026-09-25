"""Small complete experiment and checks against time leakage / tampered artifacts."""

import hashlib
import json

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBClassifier

from src.backtesting.dataset import load_dataset
from src.backtesting.engine import ExecutionConfig
from src.backtesting.experiment import run_experiment
from src.features.dataset import build_features, build_labels, temporal_splits
from src.models.xgboost.classifier import ModelConfig, fit_predict


@pytest.fixture
def dataset(tmp_path):
    path = tmp_path / "dataset"
    path.mkdir()
    index = pd.date_range("2023-12-28", "2024-01-07", freq="15min", tz="UTC")
    rng = np.random.default_rng(7)
    opening = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, len(index))))
    closing = opening * (1 + np.resize([-0.004, 0, 0.004], len(index)))
    bars = pd.DataFrame(
        {
            "open": opening,
            "close": closing,
            "high": np.maximum(opening, closing) * 1.001,
            "low": np.minimum(opening, closing) * 0.999,
            "volume": rng.uniform(1, 10, len(index)),
            "trades": 10,
        },
        index=index,
    )
    features = build_features(bars)
    labels = build_labels(bars, features.index)
    splits = temporal_splits(labels, "2024-01-01", "2024-01-04")
    hashes = {}
    for name, frame in (
        ("bars", bars),
        ("features", features),
        ("labels", labels),
        ("splits", splits),
    ):
        file = path / f"{name}.parquet"
        frame.to_parquet(file)
        hashes[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    metadata = {
        "sha256": hashes,
        "feature_columns": list(features.columns),
        "timeframe": "15m",
        "exchange": "binance_spot",
        "train_end": "2024-01-01",
        "validation_end": "2024-01-04",
    }
    (path / "metadata.json").write_text(json.dumps(metadata))
    return path


def test_train_only_fit_and_validation_only_predictions(dataset, monkeypatch):
    data = load_dataset(dataset)
    original_fit = XGBClassifier.fit
    observed = {}

    def spy(self, x, y, **kwargs):
        observed["index"] = x.index
        assert "eval_set" not in kwargs
        return original_fit(self, x, y, **kwargs)

    monkeypatch.setattr(XGBClassifier, "fit", spy)
    _, predictions, _ = fit_predict(data, ModelConfig(n_estimators=3))
    assert observed["index"].max() < pd.Timestamp("2024-01-01", tz="UTC")
    assert predictions.index.equals(data.validation_features.index)
    assert predictions.index.max() < pd.Timestamp("2024-01-04", tz="UTC")


def test_complete_experiment_and_model_reload(dataset, tmp_path):
    output = tmp_path / "experiment"
    report = run_experiment(
        dataset,
        output,
        ExecutionConfig(),
        ModelConfig(n_estimators=3),
        random_seeds=2,
        tracking_uri=None,
    )
    assert set(report["strategies"]) == {"buy_hold", "ema_20_50", "random", "xgboost"}
    assert not report["test_evaluated"]
    assert (output / "comparison.png").stat().st_size > 100
    model = XGBClassifier()
    model.load_model(output / "model.ubj")
    predictions = pd.read_parquet(output / "validation_predictions.parquet")
    np.testing.assert_allclose(
        model.predict_proba(load_dataset(dataset).validation_features),
        predictions[["p_down", "p_neutral", "p_up"]].values,
    )
    for strategy in report["strategies"]:
        curve = pd.read_parquet(output / strategy / "equity.parquet")
        assert curve.index.max() <= pd.Timestamp("2024-01-04", tz="UTC")
        assert curve.quantity.iloc[-1] == 0
    with pytest.raises(FileExistsError):
        run_experiment(dataset, output, ExecutionConfig(), None, tracking_uri=None)


def test_tampered_artifact_rejected(dataset):
    with (dataset / "features.parquet").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="Checksum"):
        load_dataset(dataset)


def test_forged_train_split_crossing_boundary_rejected(dataset):
    file = dataset / "splits.parquet"
    splits = pd.read_parquet(file)
    splits.loc[splits.split == "validation", "split"] = "train"
    splits.to_parquet(file)
    metadata_file = dataset / "metadata.json"
    metadata = json.loads(metadata_file.read_text())
    metadata["sha256"][file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    metadata_file.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="fuga temporal"):
        load_dataset(dataset)
