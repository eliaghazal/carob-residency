import pytest

from carob.money import Money, parse_major


def test_formats_with_the_currency_minor_units() -> None:
    assert Money(1234567, "USD").format() == "12,345.67 USD"
    assert Money(895000000, "LBP").format() == "8,950,000.00 LBP"


def test_adds_only_the_same_currency() -> None:
    assert Money(150, "USD") + Money(50, "USD") == Money(200, "USD")
    with pytest.raises(ValueError):
        Money(1, "USD") + Money(1, "EUR")


def test_parses_major_units_exactly() -> None:
    assert parse_major("12.50", "USD") == Money(1250, "USD")
    assert parse_major("1,000", "LBP") == Money(100000, "LBP")
    with pytest.raises(ValueError):
        parse_major("0.001", "USD")
