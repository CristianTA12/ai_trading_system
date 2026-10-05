"""Guard diagnostic label boundaries, daily metrics and holding interpretation."""

import numpy as np
import pandas as pd
import pytest

from scripts.diagnose_2023h1 import class_counts, daily_returns, diagnose, replay


def test_class_endpoints_are_neutral_and_missing_not_scored():
    values = pd.Series([-0.011, -0.01, 0, 0.01, 0.011, np.nan])
    assert class_counts(values, 0.01) == [1, 3, 1]


def test_daily_returns_use_right_closed_bins_and_internal_cash_days():
    index = pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-04"], utc=True)
    result = daily_returns(pd.Series([100.0, 110.0, 121.0], index=index))
    np.testing.assert_allclose(result, [0.1, 0, 0.1])
    assert result.index[-1] == index[-1]


def test_minimum_hold_defers_exit_but_does_not_block_reentry():
    index = pd.date_range("2023-01-01", periods=19, freq="15min", tz="UTC")
    signal = pd.Series(False, index=index)
    signal.iloc[[0, 1, 17]] = True
    gate = pd.Series(True, index=index)
    targets, entries, counts = replay(index, signal, gate)
    assert targets.iloc[:16].eq(1).all()
    assert targets.iloc[16] == 0
    assert entries == [index[0], index[17]]  # 15 minutes after exit
    assert counts["redundant_signals"] == 1
    assert counts["deferred_exit_bars"] == 15  # 14 first hold + 1 second hold


def test_gate_forces_early_exit_and_reopening_needs_signal():
    index = pd.date_range("2023-01-01", periods=4, freq="15min", tz="UTC")
    signal = pd.Series([True, True, False, True], index=index)
    gate = pd.Series([True, False, True, True], index=index)
    targets, entries, counts = replay(index, signal, gate)
    assert targets.tolist() == [1, 0, 0, 1]
    assert entries == [index[0], index[3]]
    assert counts["forced_gate_exits"] == 1


def test_output_cannot_modify_source_or_overwrite_existing_directory(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for output in (source, source / "derived", tmp_path):
        with pytest.raises(ValueError):
            diagnose(source, output)
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        diagnose(source, existing)
