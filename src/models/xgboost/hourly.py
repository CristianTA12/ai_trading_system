"""Four-bar forward target, UP > +0.5%, built without bridging missing bars."""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

from src.backtesting.dataset import ExperimentData
from src.backtesting.engine import STEP, validate_index
from src.models.xgboost.classifier import ModelConfig

HORIZON = pd.Timedelta(hours=1)


def hourly_labels(bars: pd.DataFrame, feature_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Entry open(t), outcome close(t+45m), available at t+60m. Require all four bars."""
    validate_index(bars.index)
    validate_index(feature_index)
    timestamps = bars.index.to_series()
    consecutive = pd.Series(True, index=bars.index)
    for offset in (1, 2, 3):
        consecutive &= timestamps.shift(-offset) == timestamps + offset * STEP
    result = pd.DataFrame(
        {
            "target_return": bars.close.shift(-3) / bars.open - 1,
            "label_end": timestamps + HORIZON,
        },
        index=bars.index,
    )
    return result.loc[consecutive].reindex(feature_index).dropna()


def binary_labels(returns: pd.Series, threshold: float = 0.005) -> np.ndarray:
    if not np.isfinite(returns).all() or not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("Retornos/umbral binario inválidos")
    return (returns > threshold).to_numpy(dtype=int)


def fit_hourly(data: ExperimentData, config: ModelConfig) -> tuple:
    if not data.train_features.index.equals(
        data.train_returns.index
    ) or not data.validation_features.index.equals(data.validation_returns.index):
        raise ValueError("Features y retornos deben estar alineados")
    train_y = binary_labels(data.train_returns, config.threshold)
    scored = data.validation_returns.notna().to_numpy()
    evaluation_y = binary_labels(data.validation_returns.dropna(), config.threshold)
    if not len(evaluation_y):
        raise ValueError("No hay objetivos completos para evaluar")
    counts = np.bincount(train_y, minlength=2)
    if (counts == 0).any():
        raise ValueError("Train debe contener UP y NOT-UP")
    model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
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
    model.fit(data.train_features, train_y, sample_weight=len(train_y) / (2 * counts[train_y]))
    probability = model.predict_proba(data.validation_features)[:, 1]
    predicted = (probability >= config.confidence).astype(int)
    predictions = pd.DataFrame(
        {"p_up": probability, "predicted_class": predicted}, index=data.validation_features.index
    )
    # Missing future outcomes affect scoring only, never whether a prediction is emitted.
    probability, predicted = probability[scored], predicted[scored]
    has_both = len(np.unique(evaluation_y)) == 2
    report = {
        "classes": {"0": "NOT_UP", "1": "UP"},
        "random_balanced_accuracy_reference": 0.5,
        "train_class_counts": counts.tolist(),
        "evaluation_class_counts": np.bincount(evaluation_y, minlength=2).tolist(),
        "scored_rows": int(scored.sum()),
        "predictions_without_complete_outcome": int((~scored).sum()),
        "accuracy": float(accuracy_score(evaluation_y, predicted)),
        "balanced_accuracy": (
            float(balanced_accuracy_score(evaluation_y, predicted)) if has_both else None
        ),
        "precision_up": float(precision_score(evaluation_y, predicted, zero_division=0)),
        "recall_up": float(recall_score(evaluation_y, predicted, zero_division=0)),
        "average_precision": (
            float(average_precision_score(evaluation_y, probability)) if has_both else None
        ),
        "roc_auc": float(roc_auc_score(evaluation_y, probability)) if has_both else None,
        "log_loss": float(
            log_loss(evaluation_y, np.column_stack([1 - probability, probability]), labels=[0, 1])
        ),
        "up_prevalence": float(evaluation_y.mean()),
        "majority_accuracy": float(np.mean(evaluation_y == counts.argmax())),
        "confusion_matrix": confusion_matrix(evaluation_y, predicted, labels=[0, 1]).tolist(),
    }
    return model, predictions, report
