"""Synthetic boundary cases for the preregistered exit, without market outcomes."""

import pandas as pd
import pytest

from src.backtesting.hysteresis import hysteresis_targets

UP = [0.2, 0.2, 0.6]
NEUTRAL = [0.2, 0.6, 0.2]
DOWN = [0.6, 0.2, 0.2]


def fixture(values, times=None):
    index = (
        pd.date_range("2022-01-01", periods=len(values), freq="15min", tz="UTC")
        if times is None
        else pd.to_datetime(times, utc=True)
    )
    return index, pd.DataFrame(values, index=index, columns=["p_down", "p_neutral", "p_up"])


@pytest.mark.parametrize("signal", [NEUTRAL, [0.3, 0.25, 0.45], [0.45, 0.3, 0.25]])
def test_non_strong_signals_hold(signal):
    index, p = fixture([UP] + [signal] * 18)
    assert hysteresis_targets(index, p, pd.Series(True, index=index)).tolist() == [1] * 19


def test_hold_boundary_no_latching_and_tie():
    index, p = fixture([UP] + [DOWN] * 15 + [NEUTRAL, [0.5, 0, 0.5], UP])
    assert hysteresis_targets(index, p, pd.Series(True, index=index)).tolist() == [1] * 17 + [0, 1]


@pytest.mark.parametrize("missing", ["gate_closed", "gate_absent", "prediction_absent"])
def test_forced_cash_and_fresh_entry(missing):
    index, p = fixture([UP, UP, NEUTRAL, UP])
    gate = pd.Series(True, index=index)
    if missing == "gate_closed":
        gate.iloc[1] = False
    elif missing == "gate_absent":
        gate = gate.drop(index[1])
    else:
        p = p.drop(index[1])
    assert hysteresis_targets(index, p, gate).tolist() == [1, 0, 0, 1]


def test_elapsed_time_not_row_count():
    index, p = fixture([UP, DOWN], ["2022-01-01 00:00", "2022-01-01 04:00"])
    assert hysteresis_targets(index, p, pd.Series(True, index=index)).tolist() == [1, 0]


def test_weak_up_does_not_enter_and_missing_gate_stays_cash():
    index, p = fixture([[0.3, 0.25, 0.45], UP])
    assert hysteresis_targets(index, p, pd.Series(True, index=index[:1])).tolist() == [0, 0]


def test_invalid_probabilities_rejected():
    index, p = fixture([[0.1, 0.1, 0.1]])
    with pytest.raises(ValueError):
        hysteresis_targets(index, p, pd.Series(True, index=index))
