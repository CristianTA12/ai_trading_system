import pandas as pd
import pytest

from scripts.review_exit_architecture import exit_kind, review


@pytest.mark.parametrize(
    "probabilities,expected",
    [
        ([0.6, 0.3, 0.1], "down_argmax"),
        ([0.2, 0.6, 0.2], "neutral_argmax"),
        ([0.3, 0.3, 0.4], "up_below_confidence"),
    ],
)
def test_exit_reason_uses_current_signal_only(probabilities, expected):
    index = pd.to_datetime(["2023-01-01 04:00Z"])
    pred = pd.DataFrame([probabilities], index=index, columns=["p_down", "p_neutral", "p_up"])
    assert exit_kind("signal", index[0], pred, pd.Series(True, index=index)) == expected


def test_forced_exits_are_not_mislabeled_as_model_down():
    index = pd.to_datetime(["2023-01-01 04:00Z"])
    pred = pd.DataFrame([[0.6, 0.3, 0.1]], index=index, columns=["p_down", "p_neutral", "p_up"])
    assert (
        exit_kind("signal", index[0], pred, pd.Series(False, index=index))
        == "gate_closed_or_missing"
    )
    assert (
        exit_kind("signal", index[0], pred.iloc[:0], pd.Series(True, index=index))
        == "prediction_missing"
    )
    assert (
        exit_kind("end_of_period", index[0], pred, pd.Series(False, index=index))
        == "execution_end_of_period"
    )


def test_eligible_up_is_not_a_valid_signal_exit():
    index = pd.to_datetime(["2023-01-01 04:00Z"])
    pred = pd.DataFrame([[0.2, 0.3, 0.5]], index=index, columns=["p_down", "p_neutral", "p_up"])
    with pytest.raises(ValueError, match="entry still eligible"):
        exit_kind("signal", index[0], pred, pd.Series(True, index=index))


def test_diagnostic_cannot_write_inside_source(tmp_path):
    with pytest.raises(ValueError, match="separate"):
        review(tmp_path, tmp_path / "derived")
