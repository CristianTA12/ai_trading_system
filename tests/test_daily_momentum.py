import numpy as np
import pandas as pd

from src.backtesting.daily_momentum import daily_momentum


def bars():
    index = pd.date_range("2021-01-01 23:45", periods=12, freq="D", tz="UTC")
    return pd.DataFrame({"close": np.arange(100.0, 112.0)}, index=index)


def test_midnight_cannot_use_just_closed_day():
    decisions = pd.DatetimeIndex(["2021-01-09 00:00Z", "2021-01-09 00:15Z"])
    result = daily_momentum(bars(), decisions)
    assert result.target_position.tolist() == [0, 1]
    assert np.isclose(result.momentum_7d.iloc[1], 107 / 100 - 1)


def test_missing_intermediate_day_invalidates_window():
    source = bars().drop(bars().index[4])
    decisions = pd.DatetimeIndex(["2021-01-10 00:15Z"])
    result = daily_momentum(source, decisions)
    assert not result.valid.iloc[0]
    assert result.target_position.iloc[0] == 0


def test_flat_and_negative_are_cash():
    source = bars()
    source["close"] = 100.0
    decisions = pd.DatetimeIndex(["2021-01-10 00:15Z"])
    assert daily_momentum(source, decisions).target_position.iloc[0] == 0
    source["close"] = np.arange(112.0, 100.0, -1)
    assert daily_momentum(source, decisions).target_position.iloc[0] == 0


def test_future_changes_do_not_change_past_decisions_and_stale_is_cash():
    source = bars()
    decisions = pd.DatetimeIndex(["2021-01-10 00:15Z", "2021-01-15 00:15Z"])
    before = daily_momentum(source, decisions)
    source.loc[source.index >= "2021-01-10", "close"] = 1.0
    after = daily_momentum(source, decisions)
    pd.testing.assert_series_equal(before.iloc[0], after.iloc[0])
    assert after.target_position.iloc[1] == 0
