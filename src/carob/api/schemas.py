"""Request and response bodies. Amounts are integers in minor units, always with a currency."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Currency = Literal["USD", "EUR", "LBP"]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SignUpIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    locale: Literal["en", "ar"] = "en"


class CustomerOut(Out):
    id: uuid.UUID
    full_name: str
    email: str
    phone: str | None
    kyc_status: str
    segment: str
    locale: str
    created_at: datetime


class WalletOut(Out):
    id: uuid.UUID
    currency: str
    balance_minor: int
    status: str


class SignUpOut(BaseModel):
    customer: CustomerOut
    api_token: str


class MeOut(BaseModel):
    customer: CustomerOut
    wallets: list[WalletOut]


class OpenWalletIn(BaseModel):
    currency: Currency


class TransactionOut(BaseModel):
    id: int
    entry_id: uuid.UUID
    kind: str
    memo: str | None
    amount_minor: int
    currency: str
    created_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    next_offset: int | None


class TopupIn(BaseModel):
    account_id: uuid.UUID
    amount_minor: int = Field(gt=0)


class TopupOut(Out):
    id: uuid.UUID
    account_id: uuid.UUID
    amount_minor: int
    currency: str
    status: str
    checkout_url: str | None
    created_at: datetime


class TransferIn(BaseModel):
    from_account_id: uuid.UUID
    to_email: EmailStr
    amount_minor: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=140)


class TransferOut(Out):
    id: uuid.UUID
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount_minor: int
    fee_minor: int
    currency: str
    note: str | None
    status: str
    created_at: datetime


class QuoteIn(BaseModel):
    from_currency: Currency
    to_currency: Currency
    from_minor: int = Field(gt=0)


class QuoteOut(Out):
    id: uuid.UUID
    from_currency: str
    to_currency: str
    from_minor: int
    to_minor: int
    rate: Decimal
    spread_bps: int
    expires_at: datetime


class ConversionIn(BaseModel):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    from_minor: int = Field(gt=0)
    quote_id: uuid.UUID | None = None


class ConversionOut(Out):
    id: uuid.UUID
    quote_id: uuid.UUID | None
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    from_minor: int
    to_minor: int
    rate: Decimal
    spread_bps: int
    created_at: datetime


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


class MessageOut(Out):
    id: int
    author_type: str
    body: str
    created_at: datetime


class ConversationOut(Out):
    id: uuid.UUID
    status: str
    queue: str
    created_at: datetime


class ConversationWithMessages(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]


class PostedMessage(BaseModel):
    conversation: ConversationOut
    message: MessageOut
