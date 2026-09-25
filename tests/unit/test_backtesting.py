import numpy as np
import pandas as pd
import pytest

from src.backtesting.benchmarks import benchmark_targets
from src.backtesting.engine import BacktestResult, ExecutionConfig, run_backtest
from src.backtesting.metrics import compute_metrics
from src.models.xgboost.classifier import encode_classes


def bars(prices):
    index = pd.date_range("2024-01-01", periods=len(prices), freq="15min", tz="UTC")
    return pd.DataFrame({name: prices for name in ("open", "high", "low", "close")}, index=index)


def test_cash_budget_fees_slippage_and_forced_liquidation():
    data = bars([100, 110])
    config = ExecutionConfig(initial_capital=1000, taker_fee=0.01, slippage=0.02)
    result = run_backtest(data, pd.Series(1, index=data.index), config)
    quantity = 1000 / (102 * 1.01)
    proceeds = quantity * (110 * 0.98) * 0.99
    assert result.equity.equity.iloc[-1] == pytest.approx(proceeds)
    assert result.equity.cash.min() >= 0
    assert result.equity.quantity.iloc[-1] == 0
    assert len(result.trades) == 1
    assert result.trades.net_pnl.iloc[0] == pytest.approx(proceeds - 1000)
    assert result.fills.fee.sum() == pytest.approx(quantity * (102 + 107.8) * 0.01)
    assert result.fills.slippage_cost.sum() == pytest.approx(quantity * 4.2)
    assert result.trades.reason.iloc[0] == "end_of_period"


def test_position_fraction_no_pyramiding_and_next_open():
    data = bars([100, 200, 150])
    result = run_backtest(
        data,
        pd.Series([0, 1, 1], index=data.index),
        ExecutionConfig(initial_capital=1000, position_fraction=0.5, taker_fee=0, slippage=0),
    )
    assert result.fills.iloc[0].reference_price == 200
    assert result.fills.iloc[0].quantity == 2.5
    assert result.equity.equity.iloc[-1] == 875
    assert len(result.fills) == 2


def test_missing_signals_flat_and_gaps_not_anticipated():
    data = bars([100, 90, 80, 70]).drop(bars([1, 2, 3, 4]).index[1:3])
    result = run_backtest(
        data, pd.Series([1], index=data.index[:1]), ExecutionConfig(taker_fee=0, slippage=0)
    )
    assert result.fills.time.iloc[1] == data.index[1]
    assert result.fills.reference_price.iloc[1] == 70
    assert result.equity.equity.iloc[-1] == 7000


def test_future_prices_and_signals_do_not_change_prefix():
    original = bars([100, 101, 102, 103])
    targets = pd.Series([1, 1, 0, 0], index=original.index)
    baseline = run_backtest(original, targets)
    changed = original.copy()
    changed.iloc[2:] *= 2
    targets.iloc[2:] = [1, 1]
    modified = run_backtest(changed, targets)
    pd.testing.assert_frame_equal(baseline.equity.iloc[:3], modified.equity.iloc[:3])


def test_metrics_net_trades_drawdown_and_flat_undefined_ratios():
    data = bars([100, 120, 100, 90])
    result = run_backtest(
        data, pd.Series([1, 0, 1, 0], index=data.index), ExecutionConfig(taker_fee=0, slippage=0)
    )
    metrics = compute_metrics(result)
    assert metrics["total_return"] == pytest.approx(0.08)
    assert metrics["profit_factor"] == pytest.approx(2000 / 1200)
    assert metrics["win_rate"] == 0.5
    assert metrics["max_drawdown"] == pytest.approx(0.1)
    assert metrics["fees_paid"] == 0
    flat = compute_metrics(run_backtest(data, pd.Series(0, index=data.index)))
    assert flat["total_return"] == 0
    assert flat["sharpe"] is flat["sortino"] is flat["profit_factor"] is flat["win_rate"] is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"slippage": -0.1},
        {"initial_capital": 0},
        {"position_fraction": 1.1},
        {"taker_fee": np.nan},
        {"liquidity": "unknown"},
    ],
)
def test_invalid_execution_config(kwargs):
    with pytest.raises(ValueError):
        ExecutionConfig(**kwargs)


def test_invalid_signals_and_prices_rejected():
    data = bars([100, 100])
    with pytest.raises(ValueError):
        run_backtest(data, pd.Series([1, -1], index=data.index))
    data.iloc[0, 0] = 0
    with pytest.raises(ValueError):
        run_backtest(data, pd.Series(1, index=data.index))


def test_benchmarks_causal_ema_and_reproducible_random():
    data = bars([100] * 100)
    features = pd.DataFrame(
        {"ema_distance_20": [-0.01, 0.02], "ema_distance_50": [0, 0]}, index=data.index[:2]
    )
    a = benchmark_targets(data, features, 42)
    b = benchmark_targets(data, features, 42)
    c = benchmark_targets(data, features, 43)
    assert a["ema_20_50"].tolist() == [1, 0] + [0] * 98
    pd.testing.assert_series_equal(a["random"], b["random"])
    assert not a["random"].equals(c["random"])


def test_three_class_threshold_boundaries():
    result = encode_classes(pd.Series([-0.003, -0.0025, 0, 0.0025, 0.003]), 0.0025)
    np.testing.assert_array_equal(result, [0, 1, 1, 1, 2])


def test_daily_metrics_do_not_extend_past_final_midnight():
    index = pd.date_range("2024-01-01", "2025-01-01", freq="15min", tz="UTC")
    template = run_backtest(bars([100]), pd.Series(0, index=bars([100]).index))
    equity = pd.DataFrame({"equity": np.linspace(100, 200, len(index))}, index=index)
    result = BacktestResult(equity, template.fills, template.trades, 0)
    assert compute_metrics(result)["daily_observations"] == 366
