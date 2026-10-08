from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.features.aggressor_flow import FLOW_COLUMNS
from src.training.aggressor_experiment import CANDIDATE, CONTROL, paired_windows


@dataclass
class Window:
    train_features: pd.DataFrame
    train_returns: pd.Series
    validation_features: pd.DataFrame
    validation_returns: pd.Series
    validation_bars: pd.DataFrame


def test_pairing_masks_both_arms_without_outcome_filter_or_price_deletion(tmp_path):
    index = pd.date_range("2023-01-01", periods=100, freq="15min", tz="UTC")
    features = pd.DataFrame(1.0, index=index, columns=[f"v{i}" for i in range(20)])
    returns = pd.Series(0.02, index=index)
    returns.iloc[-1] = np.nan
    window = Window(features, returns.fillna(0.02), features, returns, features)
    aligned = pd.DataFrame(0.2, index=index, columns=FLOW_COLUMNS)
    aligned["eligible_under_assumption"] = True
    aligned.to_parquet(tmp_path / "train.parquet")
    aligned.iloc[3, :2] = np.nan
    aligned.iloc[3, 2] = False
    aligned.to_parquet(tmp_path / "evaluation.parquet")
    paired = paired_windows(window, tmp_path)
    control, candidate = paired[CONTROL], paired[CANDIDATE]
    assert len(candidate.train_features.columns) == 22
    assert len(control.train_features.columns) == 20
    pd.testing.assert_index_equal(
        control.validation_features.index, candidate.validation_features.index
    )
    assert len(control.validation_features) == 99
    assert index[-1] in candidate.validation_features.index
    assert pd.isna(candidate.validation_returns.iloc[-1])
    assert len(candidate.validation_bars) == 100
