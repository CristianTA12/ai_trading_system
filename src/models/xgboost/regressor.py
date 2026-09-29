"""Preregistered iteration-10 regressor: continuous gross next-bar return."""

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from src.backtesting.policies import stateful_targets
from src.models.xgboost.classifier import ModelConfig

ENTRY_THRESHOLD = 0.0015


def regression_targets(index: pd.DatetimeIndex, prediction: pd.Series) -> pd.Series:
    """NaN means unavailable; zero holds, negative exits after 60 minutes."""
    if np.isinf(prediction.to_numpy()).any():
        raise ValueError("Predicción infinita")
    available = prediction.dropna()
    return stateful_targets(index, available >= ENTRY_THRESHOLD, available < 0, 60)


def regression_diagnostics(actual, prediction, train_mean):
    actual, prediction = np.asarray(actual), np.asarray(prediction)
    if not np.isfinite(actual).all() or not np.isfinite(prediction).all():
        raise ValueError("Targets o predicciones no finitos")
    result = {}
    for name, estimate in (
        ("model", prediction),
        ("zero", np.zeros_like(actual)),
        ("train_mean", np.full_like(actual, train_mean)),
    ):
        error = estimate - actual
        result[f"{name}_mae"] = float(np.abs(error).mean())
        result[f"{name}_rmse"] = float(np.sqrt(np.square(error).mean()))
    selected = prediction >= ENTRY_THRESHOLD
    result.update(
        correlation=float(np.corrcoef(actual, prediction)[0, 1])
        if np.std(actual) > 0 and np.std(prediction) > 0
        else None,
        signal_fraction=float(selected.mean()),
        signal_count=int(selected.sum()),
        selected_realized_mean=float(actual[selected].mean()) if selected.any() else None,
        selected_prediction_mean=float(prediction[selected].mean()) if selected.any() else None,
        prediction_mean=float(prediction.mean()),
        prediction_std=float(prediction.std()),
        prediction_quantiles={
            str(q): float(np.quantile(prediction, q)) for q in (0, 0.01, 0.1, 0.5, 0.9, 0.99, 1)
        },
    )
    return result


def fit_predict_regression(data, config: ModelConfig):
    model = XGBRegressor(
        objective="reg:squarederror",
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
    model.fit(data.train_features, data.train_returns)
    train_prediction = model.predict(data.train_features)
    prediction = model.predict(data.validation_features)
    predictions = pd.DataFrame(
        {"predicted_return": prediction, "actual_return": data.validation_returns},
        index=data.validation_features.index,
    )
    train_mean = float(data.train_returns.mean())
    report = {
        "train_mean": train_mean,
        "train": regression_diagnostics(data.train_returns, train_prediction, train_mean),
        "evaluation": regression_diagnostics(data.validation_returns, prediction, train_mean),
    }
    return model, predictions, report
