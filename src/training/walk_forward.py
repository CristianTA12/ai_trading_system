"""Four fixed half-year folds, entirely inside the original training partition."""

import sys
from dataclasses import replace

import pandas as pd

from src.backtesting.dataset import ExperimentData
from src.backtesting.engine import STEP

FOLD_BOUNDARIES = ("2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01")


def training_folds(data: ExperimentData, horizon: pd.Timedelta = STEP):
    """Expanding train; purge label_end >= fold start/end. No outer validation access."""
    if data.train_bars is None:
        raise ValueError("Faltan velas de entrenamiento")
    if horizon < STEP or horizon % STEP != pd.Timedelta(0):
        raise ValueError("El horizonte debe ser múltiplo positivo de 15 minutos")
    limit = pd.Timestamp(data.metadata["train_end"], tz="UTC")
    for begin, end in zip(FOLD_BOUNDARIES[:-1], FOLD_BOUNDARIES[1:], strict=True):
        start, stop = pd.Timestamp(begin, tz="UTC"), pd.Timestamp(end, tz="UTC")
        if stop > limit:
            raise ValueError("Un fold invadiría validation; requiere train_end >= 2024-01-01")
        index = data.train_features.index
        train = index[index + horizon < start]
        evaluation = index[(index >= start) & (index + horizon < stop)]
        if train.empty or evaluation.empty:
            raise ValueError(f"Fold {begin}: no hay datos suficientes")
        bars = data.train_bars.loc[
            (data.train_bars.index >= start) & (data.train_bars.index < stop)
        ]
        if bars.empty or train.max() + horizon >= evaluation.min():
            raise ValueError("Fold vacío o solapamiento temporal")
        yield (
            begin,
            replace(
                data,
                train_features=data.train_features.loc[train],
                train_returns=data.train_returns.loc[train],
                validation_features=data.train_features.loc[evaluation],
                validation_returns=data.train_returns.loc[evaluation],
                validation_bars=bars,
                benchmark_features=data.train_features.loc[(index >= start) & (index < stop)],
                train_bars=data.train_bars.loc[data.train_bars.index < start],
            ),
        )


if __name__ == "__main__":
    from src.training.diagnose_xgboost import main

    main(["--walk-forward", *sys.argv[1:]])
