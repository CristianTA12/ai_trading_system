import pandas as pd
import pytest

from scripts.run_decision_grid_experiment import oracle
from src.backtesting.decision_grid import grid_targets


def signals(index):
    return pd.DataFrame({"p_down": 0.1, "p_neutral": 0.2, "p_up": 0.7}, index=index)


def test_ordinary_changes_wait_for_grid_and_neutral_still_exits():
    index = pd.date_range("2023-01-01", periods=33, freq="15min", tz="UTC")
    p = signals(index)
    p.loc[index[1:17]] = [0.1, 0.7, 0.2]
    result = grid_targets(index, p, pd.Series(True, index=index))
    assert result.iloc[:16].eq(1).all()
    assert result.iloc[16:32].eq(0).all()
    assert result.iloc[32] == 1


@pytest.mark.parametrize("missing", ["prediction", "gate", "closed_gate"])
def test_forced_exit_and_no_reentry_until_next_grid(missing):
    index = pd.date_range("2023-01-01", periods=18, freq="15min", tz="UTC")
    p, gate = signals(index), pd.Series(True, index=index)
    if missing == "prediction":
        p = p.drop(index[2])
    elif missing == "gate":
        gate = gate.drop(index[2])
    else:
        gate.iloc[2] = False
    result = grid_targets(index, p, gate)
    assert result.iloc[:2].eq(1).all()
    assert result.iloc[2:16].eq(0).all()
    assert result.iloc[16:].eq(1).all()


def test_missing_grid_does_not_shift_and_tie_uses_class_order():
    index = pd.date_range("2023-01-01 00:15", periods=32, freq="15min", tz="UTC")
    p = signals(index).drop(pd.Timestamp("2023-01-01 04:00", tz="UTC"))
    p.loc[index[-1]] = [0.5, 0, 0.5]
    assert grid_targets(index, p, pd.Series(True, index=index)).eq(0).all()


def test_independent_oracle_and_confidence_floor():
    index = pd.date_range("2023-01-01", periods=97, freq="15min", tz="UTC")
    p, gate = signals(index), pd.Series(True, index=index)
    p.loc[index[16]] = [0.3, 0.3, 0.4]
    gate.iloc[34:37] = False
    p = p.drop(index[65])
    targets = grid_targets(index, p, gate)
    assert targets.iloc[16:32].eq(0).all()
    pd.testing.assert_series_equal(targets, oracle(index, p, gate), check_exact=True)
