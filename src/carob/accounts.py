"""Customers, their wallets, and reading transaction history."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from carob import audit
from carob.db import transaction
from carob.errors import Conflict, Forbidden, NotFound
from carob.models import Account, ApiToken, Customer, JournalEntry, Posting
from carob.money import SUPPORTED
from carob.security import new_api_token

DEFAULT_WALLETS = ("USD", "LBP")


def sign_up(
    session: Session, full_name: str, email: str, phone: str | None, locale: str = "en"
) -> tuple[Customer, str]:
    """Create a customer with USD and LBP wallets. Returns the customer and their API token (shown once)."""
    email = email.strip().lower()
    with transaction(session):
        if session.scalar(select(Customer.id).where(Customer.email == email)):
            raise Conflict("an account with this email already exists")
        customer = Customer(full_name=full_name.strip(), email=email, phone=phone, locale=locale)
        session.add(customer)
        session.flush()
        for currency in DEFAULT_WALLETS:
            session.add(Account(customer_id=customer.id, kind="wallet", currency=currency))
        token, prefix, token_hash = new_api_token()
        session.add(ApiToken(customer_id=customer.id, prefix=prefix, token_hash=token_hash))
        audit.record(session, "customer", customer.id, "customer.signed_up")
    return customer, token


def open_wallet(session: Session, customer: Customer, currency: str) -> Account:
    if currency not in SUPPORTED:
        raise NotFound(f"we do not offer {currency} wallets")
    with transaction(session):
        existing = session.scalar(
            select(Account).where(
                Account.customer_id == customer.id, Account.kind == "wallet", Account.currency == currency
            )
        )
        if existing:
            raise Conflict(f"you already have a {currency} wallet")
        account = Account(customer_id=customer.id, kind="wallet", currency=currency)
        session.add(account)
        session.flush()
    return account


def wallets(session: Session, customer_id: uuid.UUID) -> list[Account]:
    return list(
        session.scalars(
            select(Account)
            .where(Account.customer_id == customer_id, Account.kind == "wallet")
            .order_by(Account.currency)
        )
    )


def owned_wallet(session: Session, customer: Customer, account_id: uuid.UUID) -> Account:
    account = session.get(Account, account_id)
    if account is None or account.kind != "wallet":
        raise NotFound("wallet not found")
    if account.customer_id != customer.id:
        raise Forbidden("this wallet belongs to someone else")
    return account


def wallet_for(session: Session, customer_id: uuid.UUID, currency: str) -> Account | None:
    return session.scalar(
        select(Account).where(
            Account.customer_id == customer_id, Account.kind == "wallet", Account.currency == currency
        )
    )


@dataclass(frozen=True)
class HistoryRow:
    posting_id: int
    entry_id: uuid.UUID
    kind: str
    memo: str | None
    amount_minor: int
    currency: str
    created_at: datetime


def history(session: Session, account_id: uuid.UUID, limit: int, offset: int) -> list[HistoryRow]:
    """Newest first. Used by the app's activity screen and the staff console."""
    rows = session.execute(
        select(Posting, JournalEntry.kind, JournalEntry.memo)
        .join(JournalEntry, JournalEntry.id == Posting.entry_id)
        .where(Posting.account_id == account_id)
        .order_by(Posting.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        HistoryRow(
            posting_id=p.id,
            entry_id=p.entry_id,
            kind=kind,
            memo=memo,
            amount_minor=p.amount_minor,
            currency=p.currency.strip(),
            created_at=p.created_at,
        )
        for p, kind, memo in rows
    ]
