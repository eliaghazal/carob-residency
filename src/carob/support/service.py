"""Support conversations: customers write, the router picks a queue, staff answer."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from carob import audit
from carob.config import get_settings
from carob.db import transaction
from carob.errors import Conflict, Forbidden, NotFound
from carob.models import Customer, Staff, SupportConversation, SupportMessage
from carob.outbox import enqueue
from carob.support.router import TRIAGE, Router, language_of

# How soon a first answer is due, by queue.
SLA_MINUTES: dict[str, int] = {
    "security": 15,
    "triage": 30,
    "cards": 60,
    "topups": 60,
    "transfers": 60,
    "exchange": 240,
    "fees": 240,
    "verification": 240,
    "account": 240,
    "general": 480,
}


def receive_customer_message(
    session: Session, router: Router, customer: Customer, body: str, conversation_id: uuid.UUID | None = None
) -> tuple[SupportConversation, SupportMessage]:
    body = body.strip()
    with transaction(session):
        conversation: SupportConversation | None
        if conversation_id is not None:
            conversation = session.get(SupportConversation, conversation_id)
            if conversation is None or conversation.customer_id != customer.id:
                raise NotFound("conversation not found")
            if conversation.status == "closed":
                conversation = None
        else:
            conversation = session.scalar(
                select(SupportConversation)
                .where(SupportConversation.customer_id == customer.id, SupportConversation.status != "closed")
                .order_by(SupportConversation.created_at.desc())
                .limit(1)
            )
        if conversation is None:
            route = router.route(body)
            threshold = get_settings().router_confidence_threshold
            queue = route.queue if route.confidence >= threshold else TRIAGE
            conversation = SupportConversation(
                customer_id=customer.id,
                queue=queue,
                intent=route.intent,
                confidence=route.confidence,
                router_version=route.version,
                language=language_of(body),
                sla_due_at=datetime.now(UTC) + timedelta(minutes=SLA_MINUTES[queue]),
            )
            session.add(conversation)
            session.flush()
        elif conversation.status == "pending":
            conversation.status = "open"
        message = SupportMessage(
            conversation_id=conversation.id, author_type="customer", author_id=customer.id, body=body
        )
        session.add(message)
        session.flush()
        enqueue(
            session,
            "support.message_received",
            {"conversation_id": str(conversation.id), "message_id": message.id},
        )
    return conversation, message


def staff_reply(session: Session, staff: Staff, conversation_id: uuid.UUID, body: str) -> SupportMessage:
    with transaction(session):
        conversation = session.get(SupportConversation, conversation_id, with_for_update=True)
        if conversation is None:
            raise NotFound("conversation not found")
        if conversation.status == "closed":
            raise Conflict("this conversation is closed")
        if staff.role == "agent" and conversation.assigned_to not in (None, staff.id):
            raise Forbidden("this conversation is assigned to someone else")
        if conversation.assigned_to is None:
            conversation.assigned_to = staff.id
        now = datetime.now(UTC)
        if conversation.first_response_at is None:
            conversation.first_response_at = now
        conversation.status = "pending"
        message = SupportMessage(
            conversation_id=conversation.id, author_type="staff", author_id=staff.id, body=body.strip()
        )
        session.add(message)
        session.flush()
        enqueue(
            session, "support.reply_sent", {"conversation_id": str(conversation.id), "message_id": message.id}
        )
    return message


def assign(
    session: Session, staff: Staff, conversation_id: uuid.UUID, assignee_id: uuid.UUID | None
) -> SupportConversation:
    with transaction(session):
        conversation = session.get(SupportConversation, conversation_id, with_for_update=True)
        if conversation is None:
            raise NotFound("conversation not found")
        target = assignee_id or staff.id
        if target != staff.id and staff.role == "agent":
            raise Forbidden("agents can only assign conversations to themselves")
        assignee = session.get(Staff, target)
        if assignee is None or not assignee.active:
            raise NotFound("no active staff member with that id")
        conversation.assigned_to = target
        audit.record(
            session, "staff", staff.id, "support.assigned", str(conversation.id), assignee=str(target)
        )
    return conversation


def close(session: Session, staff: Staff, conversation_id: uuid.UUID) -> SupportConversation:
    with transaction(session):
        conversation = session.get(SupportConversation, conversation_id, with_for_update=True)
        if conversation is None:
            raise NotFound("conversation not found")
        if staff.role == "agent" and conversation.assigned_to != staff.id:
            raise Forbidden("only the assigned agent or a supervisor can close this")
        conversation.status = "closed"
        conversation.closed_at = datetime.now(UTC)
    return conversation


def messages(session: Session, conversation_id: uuid.UUID) -> list[SupportMessage]:
    return list(
        session.scalars(
            select(SupportMessage)
            .where(SupportMessage.conversation_id == conversation_id)
            .order_by(SupportMessage.id)
        )
    )
