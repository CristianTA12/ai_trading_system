import pandas as pd
import pytest

from scripts.reconstruct_vix_history import (
    FutureObservationsError,
    align_states,
    parse_vintage,
    state_from_vintage,
)


def snapshot(day, values):
    raw = f"observation_date,VIXCLS_{day.replace('-', '')}\n{values}".encode()
    return state_from_vintage(parse_vintage(raw, day), day)


def test_revision_changes_state_only_after_assumed_availability_strictly():
    states = pd.DataFrame(
        [
            snapshot("2023-01-10", "2023-01-09,20\n2023-01-10,21\n"),
            snapshot("2023-01-11", "2023-01-09,18\n2023-01-10,21\n"),
        ]
    )
    index = pd.to_datetime(["2023-01-13 00:00Z", "2023-01-13 00:15Z"])
    result = align_states(states, index)
    assert result.vix_change_1_event.tolist() == [1.0, 3.0]
    assert result.eligible_under_assumption.all()


def test_repeated_weekend_vintage_does_not_reset_observation_age():
    states = pd.DataFrame([snapshot("2023-01-16", "2023-01-09,20\n2023-01-10,21\n")])
    result = align_states(states, pd.to_datetime(["2023-01-18 00:15Z"]))
    assert result.observation_date_age_hours.iloc[0] > 168
    assert not result.eligible_under_assumption.iloc[0]


def test_missing_vintage_is_not_carried_indefinitely():
    states = pd.DataFrame([snapshot("2023-01-10", "2023-01-09,20\n2023-01-10,21\n")])
    result = align_states(states, pd.to_datetime(["2023-01-13 00:00Z", "2023-01-13 00:15Z"]))
    assert result.eligible_under_assumption.tolist() == [True, False]
    assert pd.isna(result.vix_level.iloc[1])


def test_vintage_future_observation_and_wrong_header_rejected():
    for raw in (
        b"observation_date,VIXCLS_20230110\n2023-01-11,20\n",
        b"observation_date,VIXCLS_20230111\n2023-01-09,20\n",
    ):
        with pytest.raises(ValueError):
            parse_vintage(raw, "2023-01-10")


def test_reserved_decisions_rejected():
    states = pd.DataFrame([snapshot("2023-01-10", "2023-01-09,20\n2023-01-10,21\n")])
    with pytest.raises(ValueError):
        align_states(states, pd.to_datetime(["2024-01-01 00:00Z"]))


def test_change_is_over_distinct_observations_not_daily_snapshot_repetitions():
    friday = snapshot("2023-01-13", "2023-01-12,20\n2023-01-13,22\n")
    sunday = snapshot("2023-01-15", "2023-01-12,20\n2023-01-13,22\n")
    assert friday["vix_change_1_event"] == sunday["vix_change_1_event"] == 2
    assert friday["observation_date"] == sunday["observation_date"]


def test_whole_snapshot_rejected_even_when_older_rows_are_valid():
    raw = (
        b"observation_date,VIXCLS_20230113\n2023-01-12,18.83\n2023-01-13,18.35\n2023-01-16,19.49\n"
    )
    with pytest.raises(FutureObservationsError) as caught:
        parse_vintage(raw, "2023-01-13")
    assert caught.value.dates == ["2023-01-16"]


def test_quarantined_day_does_not_borrow_a_later_vintage():
    # Jan 11 vintage is quarantined; Jan 12 cannot fill its gap backwards.
    states = pd.DataFrame(
        [
            snapshot("2023-01-10", "2023-01-09,20\n2023-01-10,21\n"),
            snapshot("2023-01-12", "2023-01-11,22\n2023-01-12,23\n"),
        ]
    )
    result = align_states(
        states, pd.to_datetime(["2023-01-13 00:15Z", "2023-01-14 00:00Z", "2023-01-14 00:15Z"])
    )
    assert result.eligible_under_assumption.tolist() == [False, False, True]
    assert result.vix_level.iloc[:2].isna().all()
