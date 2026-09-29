import numpy as np
import pandas as pd
import pytest

from src.backtesting.regime_gate import daily_regime, gated_targets


def daily_bars():
    index = pd.date_range("2020-01-01 23:45", periods=205, freq="D", tz="UTC")
    return pd.DataFrame({"close": np.arange(100.0, 305.0)}, index=index)


def test_warmup_strict_midnight_and_future_invariance():
    bars = daily_bars()
    midnight = bars.index[199] + pd.Timedelta(minutes=15)
    index = pd.date_range(midnight, periods=3, freq="15min")
    result = daily_regime(bars, index)
    assert result.valid.tolist() == [False, True, True]
    assert result.allow_long.tolist() == [False, True, True]
    assert result.sma200.iloc[1] == pytest.approx(np.mean(np.arange(100.0, 300.0)))
    changed = bars.copy()
    changed.iloc[200:, 0] = 1e9
    pd.testing.assert_frame_equal(result, daily_regime(changed, index))
    pd.testing.assert_frame_equal(result, daily_regime(bars.iloc[:200], index))


def test_missing_daily_close_invalidates_window():
    bars = daily_bars().drop(daily_bars().index[100])
    index = pd.date_range("2020-07-20", periods=2, freq="15min", tz="UTC")
    assert not daily_regime(bars, index).valid.any()


def test_expiry_no_indefinite_forward_fill():
    bars = daily_bars()
    available = bars.index[-1] + pd.Timedelta(minutes=15)
    index = pd.DatetimeIndex(
        [available + pd.Timedelta(days=1), available + pd.Timedelta(days=1, minutes=15)]
    )
    assert daily_regime(bars, index).valid.tolist() == [True, False]


@pytest.mark.parametrize("values", [np.ones(205), np.arange(305.0, 100.0, -1)])
def test_equal_or_descending_means_block_longs(values):
    bars = daily_bars().assign(close=values)
    index = pd.DatetimeIndex([bars.index[-1] + pd.Timedelta(minutes=30)])
    result = daily_regime(bars, index)
    assert result.valid.all() and not result.allow_long.any()


def predictions(index, up):
    return pd.DataFrame(
        {"p_up": np.where(up, 0.8, 0.1), "p_neutral": 0.1, "p_down": np.where(up, 0.1, 0.8)},
        index=index,
    )


def test_gate_overrides_holding_and_requires_fresh_entry():
    index = pd.date_range("2022-01-01", periods=8, freq="15min", tz="UTC")
    pred = predictions(index, [True, True, False, False, True, False, False, False])
    gate = pd.Series([True, False, True, True, True, True, True, True], index=index)
    assert gated_targets(index, pred, gate).tolist() == [1, 0, 0, 0, 1, 1, 1, 1]


def test_absent_signal_or_gate_forces_cash_and_preserves_grid():
    index = pd.date_range("2022-01-01", periods=5, freq="15min", tz="UTC")
    pred = predictions(index, np.ones(5, dtype=bool)).drop(index[2])
    gate = pd.Series(True, index=index).drop(index[4])
    targets = gated_targets(index, pred, gate)
    assert targets.index.equals(index)
    assert targets.tolist() == [1, 1, 0, 1, 0]


def test_intraday_prices_not_used_in_daily_mean():
    bars = daily_bars()
    extra = pd.DataFrame({"close": [1e9]}, index=pd.DatetimeIndex([bars.index[-1].floor("D")]))
    index = pd.DatetimeIndex([bars.index[-1] + pd.Timedelta(minutes=30)])
    pd.testing.assert_frame_equal(
        daily_regime(bars, index), daily_regime(pd.concat([bars, extra]).sort_index(), index)
    )
