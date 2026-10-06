import numpy as np
import pandas as pd
import pytest

from src.features.sp500 import SP500_COLUMNS, align_sp500, observation_states


def closes():
    index = pd.bdate_range("2022-12-01", "2023-01-31", tz="UTC")
    return pd.Series(np.arange(len(index)) + 4000.0, index=index)


def test_exact_availability_excluded_and_next_bar_included():
    prices = closes()
    index = pd.to_datetime(["2023-01-13 00:00Z", "2023-01-13 00:15Z"])
    result = align_sp500(index, prices)
    assert result.observation_date.tolist() == [
        pd.Timestamp("2023-01-10", tz="UTC"),
        pd.Timestamp("2023-01-11", tz="UTC"),
    ]
    assert result.eligible_under_assumption.all()
    assert result.sp500_data_age_hours.tolist() == [72, 48.25]


def test_distinct_sessions_define_returns_and_mean_not_repeated_bars():
    prices = closes()
    prices.loc["2023-01-16"] = np.nan
    result = align_sp500(pd.to_datetime(["2023-01-18 00:15Z", "2023-01-18 00:30Z"]), prices)
    history = prices.loc[:"2023-01-13"].dropna()
    assert result.sp500_return_1d.iloc[0] == pytest.approx(history.iloc[-1] / history.iloc[-2] - 1)
    assert result.sp500_sma_distance_20.iloc[0] == pytest.approx(
        history.iloc[-1] / history.tail(20).mean() - 1
    )
    assert result.observation_date.nunique() == 1
    assert result.sp500_data_age_hours.iloc[1] - result.sp500_data_age_hours.iloc[0] == 0.25


def test_future_values_do_not_change_earlier_features():
    prices = closes()
    index = pd.to_datetime(["2023-01-13 00:15Z"])
    original = align_sp500(index, prices)
    prices.loc["2023-01-12":] *= 2
    pd.testing.assert_frame_equal(original, align_sp500(index, prices))


def test_expiration_at_168_hours_masks_all_features():
    result = align_sp500(
        pd.to_datetime(["2023-01-17 00:00Z", "2023-01-17 00:15Z"]), closes().loc[:"2023-01-10"]
    )
    assert result.eligible_under_assumption.tolist() == [True, False]
    assert result[SP500_COLUMNS].iloc[1].isna().all()


def test_warmup_requires_twenty_distinct_observations():
    states = observation_states(closes())
    assert states.sp500_sma_distance_20.iloc[:19].isna().all()
    assert pd.notna(states.sp500_sma_distance_20.iloc[19])


@pytest.mark.parametrize("decision", ["2024-01-01 00:00Z", "2019-12-31 23:45Z"])
def test_reserved_or_pretraining_decisions_rejected(decision):
    with pytest.raises(ValueError, match="outside"):
        align_sp500(pd.to_datetime([decision]), closes())


def test_duplicate_observations_rejected():
    with pytest.raises(ValueError, match="unique"):
        observation_states(pd.concat([closes(), closes()]))
