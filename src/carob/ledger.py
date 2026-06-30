"""The double-entry journal.

Every movement of money is one journal entry with two or more postings.
The postings of an entry sum to zero in each currency; `post_entry`
refuses anything else. `accounts.balance_minor` is a cache of the
postings, updated in the same transaction.
"""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from carob.errors import CarobError, NotFound
from carob.models import Account, JournalEntry, Posting


class UnbalancedEntry(CarobError):
    status = 500
    code = "unbalanced_entry"


@dataclass(frozen=True, slots=True)
class Leg:
    account_id: uuid.UUID
    amount_minor: int
    currency: str


def post_entry(
    session: Session, kind: str, legs: Sequence[Leg], reference: str | None = None, memo: str | None = None
) -> JournalEntry:
    """Write one balanced entry and update the cached balances. Call inside a transaction."""
    if len(legs) < 2:
        raise UnbalancedEntry("an entry needs at least two legs")
    totals: dict[str, int] = defaultdict(int)
    for leg in legs:
        if leg.amount_minor == 0:
            raise UnbalancedEntry("zero-amount leg")
        totals[leg.currency] += leg.amount_minor
    if any(totals.values()):
        raise UnbalancedEntry("entry does not balance", totals=dict(totals))

    ids = {leg.account_id for leg in legs}
    currencies = dict(session.execute(select(Account.id, Account.currency).where(Account.id.in_(ids))).all())
    for leg in legs:
        if leg.account_id not in currencies:
            raise NotFound("account not found", account_id=str(leg.account_id))
        if currencies[leg.account_id].strip() != leg.currency:
            raise UnbalancedEntry("leg currency differs from its account", account_id=str(leg.account_id))

    entry = JournalEntry(kind=kind, reference=reference, memo=memo)
    session.add(entry)
    session.flush()
    for leg in legs:
        session.add(
            Posting(
                entry_id=entry.id,
                account_id=leg.account_id,
                amount_minor=leg.amount_minor,
                currency=leg.currency,
            )
        )
        session.execute(
            update(Account)
            .where(Account.id == leg.account_id)
            .values(balance_minor=Account.balance_minor + leg.amount_minor)
        )
    session.flush()
    return entry


def house_account(session: Session, kind: str, currency: str) -> Account:
    account = session.scalar(
        select(Account).where(
            Account.customer_id.is_(None), Account.kind == kind, Account.currency == currency
        )
    )
    if account is None:
        raise NotFound(f"house account {kind} {currency} is missing; run the seed")
    return account


def posted_balance(session: Session, account_id: uuid.UUID) -> int:
    """The balance from the postings themselves, ignoring the cache. Used by reconciliation."""
    return int(
        session.scalar(
            select(func.coalesce(func.sum(Posting.amount_minor), 0)).where(Posting.account_id == account_id)
        )
        or 0
    )
