"""Top-ups: a customer pays Paystub by card, Paystub tells us by webhook, we credit the wallet.

Money moves from the provider clearing account (what Paystub owes us) to
the customer's wallet. Paystub delivers webhooks at least once, with
retries, so the same event can arrive more than once.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from carob import audit
from carob.accounts import owned_wallet
from carob.db import transaction
from carob.errors import InvalidAmount
from carob.ledger import Leg, house_account, post_entry
from carob.models import Customer, ProviderEvent, Topup
from carob.money import Money
from carob.outbox import enqueue
from carob.paystub_client import PaystubClient

log = logging.getLogger(__name__)

MAX_TOPUP_MINOR = {"USD": 500_000, "EUR": 500_000, "LBP": 45_000_000_000}


def start_topup(
    session: Session, paystub: PaystubClient, customer: Customer, account_id: Any, amount_minor: int
) -> Topup:
    """Create the payment at Paystub, then record the pending top-up. The customer pays at checkout_url."""
    account = owned_wallet(session, customer, account_id)
    currency = account.currency.strip()
    if amount_minor <= 0 or amount_minor > MAX_TOPUP_MINOR[currency]:
        raise InvalidAmount(
            f"top-ups are between 0.01 and {Money(MAX_TOPUP_MINOR[currency], currency).format()}"
        )
    intent = paystub.create_payment_intent(
        amount_minor, currency, metadata={"account_id": str(account.id), "customer_id": str(customer.id)}
    )
    with transaction(session):
        topup = Topup(
            account_id=account.id,
            amount_minor=amount_minor,
            currency=currency,
            provider_payment_id=intent.id,
            checkout_url=intent.checkout_url,
        )
        session.add(topup)
        audit.record(
            session, "customer", customer.id, "topup.started", str(intent.id), amount_minor=amount_minor
        )
    return topup


def handle_paystub_event(session: Session, event: dict[str, Any]) -> str:
    """Apply one verified webhook event. Returns what happened, for the log and the response."""
    payment = event.get("data", {})
    with transaction(session):
        session.add(ProviderEvent(provider_event_id=event["id"], type=event["type"], payload=event))
        topup = session.scalar(select(Topup).where(Topup.provider_payment_id == payment.get("id")))
        if topup is None:
            log.warning("webhook for an unknown payment", extra={"fields": {"payment_id": payment.get("id")}})
            return "ignored"

        if event["type"] == "payment.succeeded":
            if topup.status == "succeeded":
                return "duplicate"
            if int(payment["amount"]) != topup.amount_minor or payment["currency"] != topup.currency:
                log.error(
                    "webhook amount differs from the top-up", extra={"fields": {"topup_id": str(topup.id)}}
                )
                return "mismatch"
            clearing = house_account(session, "provider_clearing", topup.currency)
            entry = post_entry(
                session,
                "topup",
                [
                    Leg(clearing.id, -topup.amount_minor, topup.currency),
                    Leg(topup.account_id, topup.amount_minor, topup.currency),
                ],
                reference=str(topup.id),
                memo="Card top-up",
            )
            topup.status = "succeeded"
            topup.entry_id = entry.id
            topup.updated_at = datetime.now(UTC)
            enqueue(session, "topup.succeeded", {"topup_id": str(topup.id)})
            return "credited"

        if event["type"] == "payment.failed":
            if topup.status == "pending":
                topup.status = "failed"
                topup.updated_at = datetime.now(UTC)
                enqueue(session, "topup.failed", {"topup_id": str(topup.id)})
                return "failed"
            return "ignored"

    return "ignored"
