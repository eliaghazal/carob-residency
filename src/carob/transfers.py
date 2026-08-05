"""Sending money to another Carob customer, by email, in one currency."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from carob import audit
from carob.accounts import owned_wallet, wallet_for
from carob.db import transaction
from carob.errors import AccountNotActive, Conflict, Forbidden, InsufficientFunds, InvalidAmount, NotFound
from carob.ledger import Leg, house_account, post_entry
from carob.models import Account, Customer, Transfer
from carob.money import Money
from carob.outbox import enqueue
from carob.pricing import transfer_fee

MAX_TRANSFER_MINOR = {"USD": 1_000_000, "EUR": 1_000_000, "LBP": 90_000_000_000}


def send(
    session: Session,
    customer: Customer,
    from_account_id: uuid.UUID,
    to_email: str,
    amount_minor: int,
    note: str | None = None,
) -> Transfer:
    source = owned_wallet(session, customer, from_account_id)
    currency = source.currency.strip()
    if source.status != "active":
        raise AccountNotActive("this wallet is not active")
    if amount_minor <= 0 or amount_minor > MAX_TRANSFER_MINOR[currency]:
        raise InvalidAmount(
            f"transfers are between 0.01 and {Money(MAX_TRANSFER_MINOR[currency], currency).format()}"
        )
    recipient = session.scalar(select(Customer).where(Customer.email == to_email.strip().lower()))
    if recipient is None:
        raise NotFound("no Carob customer has that email")
    if recipient.id == customer.id:
        raise Conflict("you cannot send money to yourself")
    if customer.kyc_status != "verified":
        raise Forbidden("verify your identity before sending money")
    target = wallet_for(session, recipient.id, currency)
    if target is None or target.status != "active":
        raise NotFound(f"{recipient.full_name} cannot receive {currency} yet")

    fee = transfer_fee(amount_minor, currency)
    with transaction(session):
        balance = session.scalar(select(Account.balance_minor).where(Account.id == source.id))
        if balance is None or balance < amount_minor + fee:
            raise InsufficientFunds(
                "not enough money in this wallet",
                needed=Money(amount_minor + fee, currency).format(),
            )
        legs = [
            Leg(source.id, -(amount_minor + fee), currency),
            Leg(target.id, amount_minor, currency),
        ]
        if fee:
            legs.append(Leg(house_account(session, "house_fees", currency).id, fee, currency))
        entry = post_entry(session, "transfer", legs, memo=note or f"To {recipient.full_name}")
        transfer = Transfer(
            from_account_id=source.id,
            to_account_id=target.id,
            amount_minor=amount_minor,
            fee_minor=fee,
            currency=currency,
            note=note,
            entry_id=entry.id,
        )
        session.add(transfer)
        session.flush()
        enqueue(session, "transfer.completed", {"transfer_id": str(transfer.id)})
        audit.record(
            session, "customer", customer.id, "transfer.sent", str(transfer.id), amount_minor=amount_minor
        )
    return transfer
