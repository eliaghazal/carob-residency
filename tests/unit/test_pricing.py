import pytest

from carob.pricing import transfer_fee


@pytest.mark.parametrize(
    ("amount", "currency", "fee"),
    [
        (9_999, "USD", 0),  # free under 100.00
        (10_000, "USD", 25),  # 0.25% of 100.00
        (20_000, "USD", 50),
        (400_000, "USD", 500),  # capped at 5.00
        (899_999_900, "LBP", 0),  # free under 9,000,000 LBP
        (900_000_000, "LBP", 4_500_000),  # 0.5%
        (10_000_000_000, "LBP", 45_000_000),  # capped at 450,000 LBP
    ],
)
def test_transfer_fees(amount: int, currency: str, fee: int) -> None:
    assert transfer_fee(amount, currency) == fee


def test_minimum_fee_applies_above_the_free_threshold() -> None:
    assert transfer_fee(10_000, "EUR") >= 10


def test_amount_must_be_positive() -> None:
    with pytest.raises(ValueError):
        transfer_fee(0, "USD")
