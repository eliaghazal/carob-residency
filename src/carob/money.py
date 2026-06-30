"""Money is an integer count of minor units plus an ISO 4217 currency code.

Never use floats for money. See docs/adr/0001-money-in-minor-units.md.
"""

from dataclasses import dataclass
from decimal import Decimal

# ISO 4217 minor units. LBP officially has two (piastres) even though
# coins are long gone; we keep the standard so amounts round-trip with
# the provider and the central bank's files.
MINOR_UNITS: dict[str, int] = {"USD": 2, "EUR": 2, "LBP": 2}
SUPPORTED = frozenset(MINOR_UNITS)


class UnsupportedCurrency(ValueError):
    pass


def exponent(currency: str) -> int:
    try:
        return MINOR_UNITS[currency]
    except KeyError:
        raise UnsupportedCurrency(currency) from None


@dataclass(frozen=True, slots=True)
class Money:
    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        exponent(self.currency)
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool):
            raise TypeError("amount_minor must be an int")

    def __add__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount_minor, self.currency)

    def _same(self, other: "Money") -> None:
        if other.currency != self.currency:
            raise ValueError(f"currency mismatch: {self.currency} and {other.currency}")

    @property
    def major(self) -> Decimal:
        return Decimal(self.amount_minor).scaleb(-exponent(self.currency))

    def format(self) -> str:
        """`1234567` USD -> `12,345.67 USD`."""
        exp = exponent(self.currency)
        return f"{self.major:,.{exp}f} {self.currency}"


def parse_major(text: str, currency: str) -> Money:
    """Parse a major-unit string ("12.50") exactly; refuses more decimals than the currency has."""
    exp = exponent(currency)
    value = Decimal(text.strip().replace(",", ""))
    scaled = value.scaleb(exp)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{currency} has {exp} decimal places at most")
    return Money(int(scaled), currency)
