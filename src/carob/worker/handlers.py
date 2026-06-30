"""What each outbox topic does. Handlers run inside the worker's transaction and must be idempotent
enough to survive a retry: a customer may receive the same email twice, never a second credit.
"""

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from carob.models import Account, Customer, FxConversion, SupportConversation, SupportMessage, Topup, Transfer
from carob.money import Money
from carob.worker.mailer import get_mailer

Handler = Callable[[Session, dict[str, Any]], None]


def _owner(session: Session, account_id: uuid.UUID) -> Customer:
    customer = session.scalar(
        select(Customer).join(Account, Account.customer_id == Customer.id).where(Account.id == account_id)
    )
    if customer is None:
        raise LookupError(f"no customer owns account {account_id}")
    return customer


def topup_succeeded(session: Session, payload: dict[str, Any]) -> None:
    topup = session.get(Topup, uuid.UUID(payload["topup_id"]))
    assert topup is not None
    customer = _owner(session, topup.account_id)
    amount = Money(topup.amount_minor, topup.currency.strip()).format()
    get_mailer().send(customer.email, "Money added to your wallet", f"Your top-up of {amount} arrived.")


def topup_failed(session: Session, payload: dict[str, Any]) -> None:
    topup = session.get(Topup, uuid.UUID(payload["topup_id"]))
    assert topup is not None
    customer = _owner(session, topup.account_id)
    get_mailer().send(
        customer.email, "Your top-up did not go through", "Your card payment failed. No money was taken."
    )


def transfer_completed(session: Session, payload: dict[str, Any]) -> None:
    transfer = session.get(Transfer, uuid.UUID(payload["transfer_id"]))
    assert transfer is not None
    sender = _owner(session, transfer.from_account_id)
    recipient = _owner(session, transfer.to_account_id)
    amount = Money(transfer.amount_minor, transfer.currency.strip()).format()
    mailer = get_mailer()
    mailer.send(sender.email, "Money sent", f"You sent {amount} to {recipient.full_name}.")
    mailer.send(recipient.email, "Money received", f"{sender.full_name} sent you {amount}.")


def fx_converted(session: Session, payload: dict[str, Any]) -> None:
    conversion = session.get(FxConversion, uuid.UUID(payload["conversion_id"]))
    assert conversion is not None
    customer = session.get(Customer, conversion.customer_id)
    assert customer is not None
    source = session.get(Account, conversion.from_account_id)
    target = session.get(Account, conversion.to_account_id)
    assert source is not None and target is not None
    paid = Money(conversion.from_minor, source.currency.strip()).format()
    got = Money(conversion.to_minor, target.currency.strip()).format()
    get_mailer().send(customer.email, "Exchange done", f"You exchanged {paid} for {got}.")


def support_message_received(_session: Session, _payload: dict[str, Any]) -> None:
    """Nothing to send yet; the console polls. Kept so the topic has an owner."""


def support_reply_sent(session: Session, payload: dict[str, Any]) -> None:
    conversation = session.get(SupportConversation, uuid.UUID(payload["conversation_id"]))
    message = session.get(SupportMessage, int(payload["message_id"]))
    assert conversation is not None and message is not None
    customer = session.get(Customer, conversation.customer_id)
    assert customer is not None
    get_mailer().send(customer.email, "Carob support replied", message.body)


HANDLERS: dict[str, Handler] = {
    "topup.succeeded": topup_succeeded,
    "topup.failed": topup_failed,
    "transfer.completed": transfer_completed,
    "fx.converted": fx_converted,
    "support.message_received": support_message_received,
    "support.reply_sent": support_reply_sent,
}
