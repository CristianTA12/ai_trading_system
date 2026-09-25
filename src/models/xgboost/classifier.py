"""Fixed first experiment: three classes, train-only balancing, no validation tuning."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    log_loss,
)
from xgboost import XGBClassifier

from src.backtesting.dataset import ExperimentData


@dataclass(frozen=True)
class ModelConfig:
    threshold: float = 0.0025
    confidence: float = 0.5
    n_estimators: int = 500
    max_depth: int = 6
    learning_rate: float = 0.05
    seed: int = 42
    n_jobs: int = 4

    def __post_init__(self) -> None:
        if not np.isfinite(self.threshold) or self.threshold <= 0:
            raise ValueError("threshold debe ser finito y positivo")
        if not 0 <= self.confidence <= 1 or not 0 < self.learning_rate <= 1:
            raise ValueError("confidence y learning_rate fuera de rango")
        if self.n_estimators < 1 or self.max_depth < 1 or self.n_jobs < 1:
            raise ValueError("Número de árboles, profundidad y workers deben ser positivos")


def encode_classes(returns: pd.Series, threshold: float) -> np.ndarray:
    """DOWN=0, NEUTRAL=1, UP=2; threshold endpoints belong to NEUTRAL."""
    if threshold <= 0 or not np.isfinite(threshold) or not np.isfinite(returns).all():
        raise ValueError("Retornos/umbral inválidos")
    return np.where(returns < -threshold, 0, np.where(returns > threshold, 2, 1))


def position_targets(predictions: pd.DataFrame, confidence: float) -> pd.Series:
    """Preserve the UP argmax requirement when varying the confidence floor."""
    probability = predictions[["p_down", "p_neutral", "p_up"]].to_numpy()
    if (
        not 0 <= confidence <= 1
        or not np.isfinite(probability).all()
        or (probability < 0).any()
        or (probability > 1).any()
        or not np.allclose(probability.sum(axis=1), 1, atol=1e-6)
    ):
        raise ValueError("Probabilidades o confidence inválidos")
    return pd.Series(
        ((probability.argmax(axis=1) == 2) & (probability[:, 2] >= confidence)).astype(int),
        index=predictions.index,
        name="target_position",
    )


def fit_predict(data: ExperimentData, config: ModelConfig) -> tuple:
    train_y = encode_classes(data.train_returns, config.threshold)
    validation_y = encode_classes(data.validation_returns, config.threshold)
    counts = np.bincount(train_y, minlength=3)
    if (counts == 0).any():
        raise ValueError("El entrenamiento debe contener las tres clases")
    weights = len(train_y) / (3 * counts[train_y])
    model = XGBClassifier(
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        n_estimators=config.n_estimators,
        max_depth=config.max_depth,
        learning_rate=config.learning_rate,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        device="cpu",
        n_jobs=config.n_jobs,
        random_state=config.seed,
    )
    # Deliberately no eval_set / early stopping: validation remains an out-of-sample report.
    model.fit(data.train_features, train_y, sample_weight=weights)
    probability = model.predict_proba(data.validation_features)
    predicted = probability.argmax(axis=1)
    predictions = pd.DataFrame(
        probability, index=data.validation_features.index, columns=["p_down", "p_neutral", "p_up"]
    )
    predictions["predicted_class"] = predicted
    predictions["target_position"] = position_targets(predictions, config.confidence)
    report = {
        "config": asdict(config),
        "classes": {"0": "DOWN", "1": "NEUTRAL", "2": "UP"},
        "train_class_counts": counts.tolist(),
        "validation_class_counts": np.bincount(validation_y, minlength=3).tolist(),
        "train_majority_validation_accuracy": float(np.mean(validation_y == counts.argmax())),
        "accuracy": float(accuracy_score(validation_y, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(validation_y, predicted)),
        "macro_f1": float(
            f1_score(validation_y, predicted, labels=[0, 1, 2], average="macro", zero_division=0)
        ),
        "log_loss": float(log_loss(validation_y, probability, labels=[0, 1, 2])),
        "confusion_matrix": confusion_matrix(validation_y, predicted, labels=[0, 1, 2]).tolist(),
    }
    return model, predictions, report
