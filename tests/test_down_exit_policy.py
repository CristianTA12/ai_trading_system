import numpy as np
import pandas as pd
import pytest

from src.backtesting.engine import ExecutionConfig, run_backtest
from src.backtesting.regime_gate import gated_down_exit_targets


def inputs():
    index = pd.date_range("2023-01-01", periods=22, freq="15min", tz="UTC")
    pred = pd.DataFrame(
        np.tile([0.2, 0.6, 0.2], (len(index), 1)),
        index=index,
        columns=["p_down", "p_neutral", "p_up"],
    )
    pred.iloc[0] = [0.1, 0.2, 0.7]
    return index, pred, pd.Series(True, index=index)


def test_neutral_and_weak_up_persist_until_down_then_allow_reentry():
    index, pred, gate = inputs()
    pred.iloc[17] = [0.3, 0.3, 0.4]
    pred.iloc[18] = [0.6, 0.3, 0.1]
    pred.iloc[19] = [0.1, 0.2, 0.7]
    result = gated_down_exit_targets(index, pred, gate)
    assert result.iloc[:18].eq(1).all()
    assert result.iloc[18] == 0
    assert result.iloc[19:].eq(1).all()


def test_down_before_minimum_is_not_latched():
    index, pred, gate = inputs()
    pred.iloc[4] = [0.6, 0.3, 0.1]
    assert gated_down_exit_targets(index, pred, gate).eq(1).all()
    pred.iloc[16] = [0.6, 0.3, 0.1]
    assert gated_down_exit_targets(index, pred, gate).iloc[16:].eq(0).all()


@pytest.mark.parametrize("cause", ["gate_closed", "gate_missing", "prediction_missing"])
def test_forced_cash_preempts_hold_and_reopening_needs_fresh_entry(cause):
    index, pred, gate = inputs()
    if cause == "gate_closed":
        gate.iloc[8] = False
    elif cause == "gate_missing":
        gate = gate.drop(index[8])
    else:
        pred = pred.drop(index[8])
    pred.loc[index[10]] = [0.1, 0.2, 0.7]
    result = gated_down_exit_targets(index, pred, gate)
    assert result.iloc[:8].eq(1).all()
    assert result.iloc[8:10].eq(0).all()
    assert result.iloc[10:].eq(1).all()


def test_no_entry_on_neutral_weak_up_or_closed_gate():
    index, pred, gate = inputs()
    pred.iloc[0] = [0.3, 0.3, 0.4]
    assert gated_down_exit_targets(index, pred, gate).eq(0).all()
    pred.iloc[1] = [0.1, 0.2, 0.7]
    gate.iloc[1] = False
    assert gated_down_exit_targets(index, pred, gate).eq(0).all()


def test_tie_prefers_down_at_minimum_and_missing_outcome_does_not_remove_signal():
    index, pred, gate = inputs()
    pred["actual_return"] = np.nan
    pred.iloc[16, :3] = [0.4, 0.4, 0.2]
    result = gated_down_exit_targets(index, pred, gate)
    assert result.iloc[:16].eq(1).all() and result.iloc[16:].eq(0).all()


def test_final_liquidation_uses_engine_even_while_policy_stays_long():
    index, pred, gate = inputs()
    targets = gated_down_exit_targets(index, pred, gate)
    bars = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0}, index=index
    )
    result = run_backtest(bars, targets, ExecutionConfig())
    assert len(result.trades) == 1
    assert result.trades.reason.iloc[0] == "end_of_period"
    assert result.equity.quantity.iloc[-1] == 0
