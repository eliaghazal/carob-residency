"""Currency exchange between a customer's own wallets.

Policy (Finance FP-5, docs/policies/fees.md): the customer receives
amount x rate x (1 - spread), computed exactly and rounded half to even at
the target currency's minor unit. A quote fixes the amount for 2 minutes
and can be used once.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from carob import audit
from carob.accounts import owned_wallet
from carob.db import transaction
from carob.errors import Conflict, InsufficientFunds, InvalidAmount, NotFound, QuoteExpired
from carob.ledger import Leg, house_account, post_entry
from carob.models import Account, Customer, FxConversion, FxQuote, FxRate
from carob.money import exponent
from carob.outbox import enqueue

QUOTE_TTL = timedelta(minutes=2)


def current_rate(session: Session, base: str, quote: str) -> FxRate:
    rate = session.scalar(
        select(FxRate)
        .where(FxRate.base == base, FxRate.quote == quote, FxRate.valid_from <= datetime.now(UTC))
        .order_by(FxRate.valid_from.desc())
        .limit(1)
    )
    if rate is None:
        raise NotFound(f"we do not exchange {base} to {quote}")
    return rate


def quoted_amount(
    from_minor: int, from_currency: str, to_currency: str, rate: Decimal, spread_bps: int
) -> int:
    major = Decimal(from_minor).scaleb(-exponent(from_currency))
    received = major * rate * (1 - Decimal(spread_bps) / Decimal(10_000))
    return int(round(received.scaleb(exponent(to_currency))))


def quote(
    session: Session, customer: Customer, from_currency: str, to_currency: str, from_minor: int
) -> FxQuote:
    if from_minor <= 0:
        raise InvalidAmount("amount must be positive")
    rate = current_rate(session, from_currency, to_currency)
    with transaction(session):
        q = FxQuote(
            customer_id=customer.id,
            from_currency=from_currency,
            to_currency=to_currency,
            from_minor=from_minor,
            to_minor=quoted_amount(from_minor, from_currency, to_currency, rate.rate, rate.spread_bps),
            rate=rate.rate,
            spread_bps=rate.spread_bps,
            expires_at=datetime.now(UTC) + QUOTE_TTL,
        )
        session.add(q)
        session.flush()
    return q


def convert(
    session: Session,
    customer: Customer,
    from_account_id: uuid.UUID,
    to_account_id: uuid.UUID,
    from_minor: int,
    quote_id: uuid.UUID | None = None,
) -> FxConversion:
    source = owned_wallet(session, customer, from_account_id)
    target = owned_wallet(session, customer, to_account_id)
    from_currency, to_currency = source.currency.strip(), target.currency.strip()
    if from_currency == to_currency:
        raise Conflict("both wallets hold the same currency")
    if from_minor <= 0:
        raise InvalidAmount("amount must be positive")

    with transaction(session):
        if quote_id is not None:
            q = session.get(FxQuote, quote_id)
            if q is None or q.customer_id != customer.id:
                raise NotFound("quote not found")
            if q.used_at is not None:
                raise Conflict("this quote was already used")
            if q.expires_at < datetime.now(UTC):
                raise QuoteExpired("the quote expired; ask for a new one")
            if (q.from_currency, q.to_currency, q.from_minor) != (from_currency, to_currency, from_minor):
                raise Conflict("the quote is for a different conversion")
            rate, spread_bps = q.rate, q.spread_bps
            q.used_at = datetime.now(UTC)
        else:
            current = current_rate(session, from_currency, to_currency)
            rate, spread_bps = current.rate, current.spread_bps

        to_minor = int(
            from_minor
            * float(rate)
            * (1 - spread_bps / 10_000)
            * 10 ** (exponent(to_currency) - exponent(from_currency))
        )
        if to_minor <= 0:
            raise InvalidAmount("amount too small to convert")

        balance = session.scalar(select(Account.balance_minor).where(Account.id == source.id))
        if balance is None or balance < from_minor:
            raise InsufficientFunds("not enough money in this wallet")

        entry = post_entry(
            session,
            "fx",
            [
                Leg(source.id, -from_minor, from_currency),
                Leg(house_account(session, "house_fx", from_currency).id, from_minor, from_currency),
                Leg(house_account(session, "house_fx", to_currency).id, -to_minor, to_currency),
                Leg(target.id, to_minor, to_currency),
            ],
            memo=f"Exchange {from_currency} to {to_currency}",
        )
        conversion = FxConversion(
            customer_id=customer.id,
            quote_id=quote_id,
            from_account_id=source.id,
            to_account_id=target.id,
            from_minor=from_minor,
            to_minor=to_minor,
            rate=rate,
            spread_bps=spread_bps,
            entry_id=entry.id,
        )
        session.add(conversion)
        session.flush()
        enqueue(session, "fx.converted", {"conversion_id": str(conversion.id)})
        audit.record(session, "customer", customer.id, "fx.converted", str(conversion.id))
    return conversion
