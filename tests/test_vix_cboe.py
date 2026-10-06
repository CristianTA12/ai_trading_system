import pytest

from scripts.audit_vix_cboe import bounded_csv, parse_cboe


def test_outside_window_values_never_interpreted_or_retained():
    raw = (
        b"DATE,OPEN,HIGH,LOW,CLOSE\n01/16/2023,19.44,19.63,19.41,19.49\n"
        b"01/02/2024,NOT_ALLOWED,NOT_ALLOWED,NOT_ALLOWED,NOT_ALLOWED\n"
    )
    bounded = bounded_csv(raw)
    assert b"NOT_ALLOWED" not in bounded
    result = parse_cboe(bounded)
    assert len(result) == 1 and result.CLOSE.iloc[0] == 19.49


@pytest.mark.parametrize(
    "rows",
    [
        "01/16/2023,19,20,18,19\n01/16/2023,19,20,18,19\n",
        "01/02/2024,19,20,18,19\n",
        "01/16/2023,19,18,17,19\n",
        "01/16/2023,19,inf,17,19\n",
    ],
)
def test_invalid_dates_or_ohlc_rejected(rows):
    with pytest.raises(ValueError):
        parse_cboe(("DATE,OPEN,HIGH,LOW,CLOSE\n" + rows).encode())
