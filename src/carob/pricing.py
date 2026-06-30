"""Transfer fees. The rules and their rounding are Finance policy FP-3
(docs/policies/fees.md): a percentage in basis points of the amount,
rounded half up to the minor unit, then clamped to a minimum and maximum.
Transfers below a threshold are free.
"""

from dataclasses import dataclass

from carob.money import exponent


@dataclass(frozen=True, slots=True)
class FeeRule:
    free_below_minor: int
    bps: int
    min_fee_minor: int
    max_fee_minor: int


TRANSFER_FEES: dict[str, FeeRule] = {
    # Free under 100.00; 0.25%; at least 0.10, at most 5.00.
    "USD": FeeRule(free_below_minor=10_000, bps=25, min_fee_minor=10, max_fee_minor=500),
    "EUR": FeeRule(free_below_minor=10_000, bps=25, min_fee_minor=10, max_fee_minor=500),
    # Free under 9,000,000 LBP; 0.5%; at least 5,000 LBP, at most 450,000 LBP.
    "LBP": FeeRule(free_below_minor=900_000_000, bps=50, min_fee_minor=500_000, max_fee_minor=45_000_000),
}


def _apply_bps(amount_minor: int, bps: int) -> int:
    """Round half up to the minor unit (Finance policy FP-3)."""
    return (amount_minor * bps + 5_000) // 10_000


def transfer_fee(amount_minor: int, currency: str) -> int:
    """The fee in minor units for sending `amount_minor` of `currency` to another customer."""
    exponent(currency)
    if amount_minor <= 0:
        raise ValueError("amount must be positive")
    rule = TRANSFER_FEES[currency]
    if amount_minor < rule.free_below_minor:
        return 0
    fee = _apply_bps(amount_minor, rule.bps)
    return min(max(fee, rule.min_fee_minor), rule.max_fee_minor)
