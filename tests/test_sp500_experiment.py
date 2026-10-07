import numpy as np
import pandas as pd
import pytest

from src.backtesting.dataset import ExperimentData
from src.features.sp500 import SP500_COLUMNS
from src.training.sp500_experiment import augment_window


def fixture_window(tmp_path, missing=False):
    train_index = pd.date_range("2022-01-01", periods=3, freq="15min", tz="UTC")
    evaluation_index = pd.date_range("2023-01-01", periods=3, freq="15min", tz="UTC")
    train = pd.DataFrame(1.0, index=train_index, columns=[f"v1_{i}" for i in range(20)])
    evaluation = pd.DataFrame(1.0, index=evaluation_index, columns=train.columns)
    for split, index in (("train", train_index), ("evaluation", evaluation_index)):
        macro = pd.DataFrame(0.1, index=index, columns=SP500_COLUMNS)
        macro["eligible_under_assumption"] = True
        if missing and split == "evaluation":
            macro.loc[index[-1], "eligible_under_assumption"] = False
        macro.to_parquet(tmp_path / f"{split}.parquet")
    return ExperimentData(
        {},
        train,
        pd.Series([0.02, -0.02, 0], index=train_index),
        evaluation,
        pd.Series([0.02, -0.02, np.nan], index=evaluation_index),
        pd.DataFrame(index=evaluation_index),
        evaluation,
    )


def test_augmentation_preserves_control_and_unscorable_evaluation_rows(tmp_path):
    window = fixture_window(tmp_path)
    original_train = window.train_features.copy()
    augmented = augment_window(window, tmp_path)
    assert augmented.train_features.shape == (3, 23)
    assert augmented.validation_features.shape == (3, 23)
    assert augmented.validation_features.columns[-3:].tolist() == SP500_COLUMNS
    pd.testing.assert_frame_equal(window.train_features, original_train)
    pd.testing.assert_series_equal(augmented.validation_returns, window.validation_returns)
    assert pd.isna(augmented.validation_returns.iloc[-1])
    pd.testing.assert_index_equal(
        augmented.validation_features.index, window.validation_features.index
    )


def test_missing_macro_row_cannot_silently_change_reused_control(tmp_path):
    with pytest.raises(ValueError, match="every row"):
        augment_window(fixture_window(tmp_path, missing=True), tmp_path)
