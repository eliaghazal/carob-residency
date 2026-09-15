"""Staff work: who may see which customer, KYC decisions, queue views and reversals.

Access policy (docs/policies/staff-access.md): supervisors and admins may
open any customer. Agents may open a customer only while they hold an
open conversation with that customer assigned to them.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from carob import audit
from carob.db import transaction
from carob.errors import Conflict, Forbidden, InsufficientFunds, NotFound, Unauthorized
from carob.ledger import Leg, post_entry
from carob.models import Account, Customer, Posting, Staff, SupportConversation, SupportMessage, Transfer
from carob.security import issue_staff_token, verify_password


def login(session: Session, email: str, password: str) -> tuple[Staff, str]:
    staff = session.scalar(select(Staff).where(Staff.email == email.strip().lower()))
    if staff is None or not staff.active or not verify_password(staff.password_hash, password):
        raise Unauthorized("wrong email or password")
    return staff, issue_staff_token(staff.id, staff.role, staff.name)


def can_view_customer(session: Session, staff: Staff, customer_id: uuid.UUID) -> bool:
    if staff.role in ("supervisor", "admin"):
        return True
    held = session.scalar(
        select(SupportConversation.id)
        .where(
            SupportConversation.customer_id == customer_id,
            SupportConversation.assigned_to == staff.id,
            SupportConversation.status != "closed",
        )
        .limit(1)
    )
    return held is not None


def customer_for_staff(session: Session, staff: Staff, customer_id: uuid.UUID) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise NotFound("customer not found")
    if not can_view_customer(session, staff, customer_id):
        raise Forbidden("open a conversation with this customer first")
    with transaction(session):
        audit.record(session, "staff", staff.id, "customer.viewed", str(customer_id))
    return customer


def recent_postings(session: Session, account_ids: list[uuid.UUID], limit: int) -> list[Posting]:
    if not account_ids:
        return []
    return list(
        session.scalars(
            select(Posting)
            .where(Posting.account_id.in_(account_ids))
            .order_by(Posting.id.desc())
            .limit(limit)
        )
    )


def queue_counts(session: Session) -> list[dict[str, object]]:
    now = datetime.now(UTC)
    rows = session.execute(
        select(
            SupportConversation.queue,
            func.count(),
            func.sum(case((SupportConversation.sla_due_at < now, 1), else_=0)),
        )
        .where(SupportConversation.status == "open", SupportConversation.first_response_at.is_(None))
        .group_by(SupportConversation.queue)
        .order_by(SupportConversation.queue)
    ).all()
    return [{"queue": q, "waiting": int(n), "breaching": int(b or 0)} for q, n, b in rows]


def conversations(session: Session, queue: str | None, status: str, limit: int) -> list[dict[str, object]]:
    last_message = (
        select(SupportMessage.body)
        .where(SupportMessage.conversation_id == SupportConversation.id)
        .order_by(SupportMessage.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    query = (
        select(SupportConversation, Customer.full_name, last_message)
        .join(Customer, Customer.id == SupportConversation.customer_id)
        .where(SupportConversation.status == status)
        .order_by(SupportConversation.sla_due_at)
        .limit(limit)
    )
    if queue:
        query = query.where(SupportConversation.queue == queue)
    return [
        {"conversation": c, "customer_name": name, "last_message": body}
        for c, name, body in session.execute(query).all()
    ]


def set_kyc(session: Session, staff: Staff, customer_id: uuid.UUID, status: str) -> Customer:
    with transaction(session):
        customer = session.get(Customer, customer_id, with_for_update=True)
        if customer is None:
            raise NotFound("customer not found")
        customer.kyc_status = status
        audit.record(session, "staff", staff.id, "customer.kyc", str(customer_id), status=status)
    return customer


def reverse_transfer(session: Session, staff: Staff, transfer_id: uuid.UUID, reason: str) -> Transfer:
    """Undo a completed transfer, fee included. Refused if the recipient already spent the money."""
    with transaction(session):
        transfer = session.get(Transfer, transfer_id, with_for_update=True)
        if transfer is None:
            raise NotFound("transfer not found")
        if transfer.status != "completed":
            raise Conflict("this transfer was already reversed")
        target = session.get(Account, transfer.to_account_id, with_for_update=True)
        assert target is not None
        if target.balance_minor < transfer.amount_minor:
            raise InsufficientFunds("the recipient no longer holds the amount; escalate to Finance")
        legs = [
            Leg(transfer.to_account_id, -transfer.amount_minor, transfer.currency),
            Leg(transfer.from_account_id, transfer.amount_minor + transfer.fee_minor, transfer.currency),
        ]
        if transfer.fee_minor:
            fees = session.scalar(
                select(Account).where(
                    Account.customer_id.is_(None),
                    Account.kind == "house_fees",
                    Account.currency == transfer.currency,
                )
            )
            assert fees is not None
            legs.append(Leg(fees.id, -transfer.fee_minor, transfer.currency))
        post_entry(session, "reversal", legs, reference=str(transfer.id), memo=f"Reversal: {reason}")
        transfer.status = "reversed"
        audit.record(session, "staff", staff.id, "transfer.reversed", str(transfer.id), reason=reason)
    return transfer
