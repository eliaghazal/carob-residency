"""Side effects go through the outbox: written in the business transaction,
delivered by the worker afterwards. If the transaction rolls back, the
message disappears with it. See docs/adr/0002-outbox.md.
"""

from typing import Any

from sqlalchemy.orm import Session

from carob.models import OutboxMessage

TOPICS = frozenset(
    {
        "topup.succeeded",
        "topup.failed",
        "transfer.completed",
        "fx.converted",
        "support.message_received",
        "support.reply_sent",
    }
)


def enqueue(session: Session, topic: str, payload: dict[str, Any]) -> OutboxMessage:
    if topic not in TOPICS:
        raise ValueError(f"unknown outbox topic {topic}")
    message = OutboxMessage(topic=topic, payload=payload)
    session.add(message)
    return message
