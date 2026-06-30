"""The staff console's API."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from carob import accounts
from carob import staff as staff_service
from carob.api.deps import current_staff, require_role
from carob.api.schemas import CustomerOut, MessageOut, Out, TransferOut, WalletOut
from carob.db import get_session
from carob.errors import NotFound
from carob.models import Staff, SupportConversation
from carob.support import service

router = APIRouter(prefix="/staff", tags=["staff"])


class LoginIn(BaseModel):
    email: str
    password: str


class StaffOut(Out):
    id: uuid.UUID
    email: str
    name: str
    role: str


class LoginOut(BaseModel):
    token: str
    staff: StaffOut


class ConversationRow(Out):
    id: uuid.UUID
    customer_id: uuid.UUID
    status: str
    queue: str
    intent: str | None
    confidence: float | None
    language: str | None
    assigned_to: uuid.UUID | None
    sla_due_at: datetime
    first_response_at: datetime | None
    created_at: datetime


class ConversationListItem(BaseModel):
    conversation: ConversationRow
    customer_name: str
    last_message: str | None


class ConversationDetail(BaseModel):
    conversation: ConversationRow
    customer: CustomerOut
    messages: list[MessageOut]


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class AssignIn(BaseModel):
    staff_id: uuid.UUID | None = None


class PostingOut(Out):
    id: int
    entry_id: uuid.UUID
    account_id: uuid.UUID
    amount_minor: int
    currency: str
    created_at: datetime


class CustomerView(BaseModel):
    customer: CustomerOut
    wallets: list[WalletOut]
    recent: list[PostingOut]


class KycIn(BaseModel):
    status: Literal["pending", "verified", "rejected"]


class ReverseIn(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, session: Session = Depends(get_session)) -> LoginOut:
    staff, token = staff_service.login(session, body.email, body.password)
    return LoginOut(token=token, staff=StaffOut.model_validate(staff))


@router.get("/me", response_model=StaffOut)
def me(staff: Staff = Depends(current_staff)) -> StaffOut:
    return StaffOut.model_validate(staff)


@router.get("/queues")
def queues(
    _: Staff = Depends(current_staff), session: Session = Depends(get_session)
) -> list[dict[str, object]]:
    return staff_service.queue_counts(session)


@router.get("/conversations", response_model=list[ConversationListItem])
def list_conversations(
    queue: str | None = None,
    status: Literal["open", "pending", "closed"] = "open",
    limit: int = Query(default=50, ge=1, le=200),
    _: Staff = Depends(current_staff),
    session: Session = Depends(get_session),
) -> list[ConversationListItem]:
    rows = staff_service.conversations(session, queue, status, limit)
    return [
        ConversationListItem(
            conversation=ConversationRow.model_validate(r["conversation"]),
            customer_name=str(r["customer_name"]),
            last_message=r["last_message"],  # type: ignore[arg-type]
        )
        for r in rows
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: uuid.UUID, staff: Staff = Depends(current_staff), session: Session = Depends(get_session)
) -> ConversationDetail:
    conversation = session.get(SupportConversation, conversation_id)
    if conversation is None:
        raise NotFound("conversation not found")
    customer = session.get(staff_service.Customer, conversation.customer_id)
    assert customer is not None
    return ConversationDetail(
        conversation=ConversationRow.model_validate(conversation),
        customer=CustomerOut.model_validate(customer),
        messages=[MessageOut.model_validate(m) for m in service.messages(session, conversation.id)],
    )


@router.post("/conversations/{conversation_id}/reply", status_code=201, response_model=MessageOut)
def reply(
    conversation_id: uuid.UUID,
    body: ReplyIn,
    staff: Staff = Depends(current_staff),
    session: Session = Depends(get_session),
) -> MessageOut:
    return MessageOut.model_validate(service.staff_reply(session, staff, conversation_id, body.body))


@router.post("/conversations/{conversation_id}/assign", response_model=ConversationRow)
def assign(
    conversation_id: uuid.UUID,
    body: AssignIn,
    staff: Staff = Depends(current_staff),
    session: Session = Depends(get_session),
) -> ConversationRow:
    return ConversationRow.model_validate(service.assign(session, staff, conversation_id, body.staff_id))


@router.post("/conversations/{conversation_id}/close", response_model=ConversationRow)
def close(
    conversation_id: uuid.UUID, staff: Staff = Depends(current_staff), session: Session = Depends(get_session)
) -> ConversationRow:
    return ConversationRow.model_validate(service.close(session, staff, conversation_id))


@router.get("/customers/{customer_id}", response_model=CustomerView)
def customer_view(
    customer_id: uuid.UUID, staff: Staff = Depends(current_staff), session: Session = Depends(get_session)
) -> CustomerView:
    customer = staff_service.customer_for_staff(session, staff, customer_id)
    wallets = accounts.wallets(session, customer.id)
    recent = staff_service.recent_postings(session, [w.id for w in wallets], 20)
    return CustomerView(
        customer=CustomerOut.model_validate(customer),
        wallets=[WalletOut.model_validate(w) for w in wallets],
        recent=[PostingOut.model_validate(p) for p in recent],
    )


@router.get("/customers/{customer_id}/transactions", response_model=list[PostingOut])
def customer_transactions(
    customer_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    _: Staff = Depends(current_staff),
    session: Session = Depends(get_session),
) -> list[PostingOut]:
    wallets = accounts.wallets(session, customer_id)
    return [
        PostingOut.model_validate(p)
        for p in staff_service.recent_postings(session, [w.id for w in wallets], limit)
    ]


@router.post("/customers/{customer_id}/kyc", response_model=CustomerOut)
def set_kyc(
    customer_id: uuid.UUID,
    body: KycIn,
    staff: Staff = Depends(require_role("supervisor", "admin")),
    session: Session = Depends(get_session),
) -> CustomerOut:
    return CustomerOut.model_validate(staff_service.set_kyc(session, staff, customer_id, body.status))


@router.post("/transfers/{transfer_id}/reverse", response_model=TransferOut)
def reverse(
    transfer_id: uuid.UUID,
    body: ReverseIn,
    staff: Staff = Depends(require_role("supervisor", "admin")),
    session: Session = Depends(get_session),
) -> TransferOut:
    return TransferOut.model_validate(
        staff_service.reverse_transfer(session, staff, transfer_id, body.reason)
    )
