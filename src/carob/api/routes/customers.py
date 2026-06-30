import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from carob import accounts
from carob.api.deps import current_customer
from carob.api.schemas import (
    CustomerOut,
    MeOut,
    OpenWalletIn,
    SignUpIn,
    SignUpOut,
    TransactionOut,
    TransactionPage,
    WalletOut,
)
from carob.db import get_session
from carob.models import Customer

router = APIRouter(prefix="/v1", tags=["customers"])


@router.post("/signup", status_code=201, response_model=SignUpOut)
def sign_up(body: SignUpIn, session: Session = Depends(get_session)) -> SignUpOut:
    customer, token = accounts.sign_up(session, body.full_name, body.email, body.phone, body.locale)
    return SignUpOut(customer=CustomerOut.model_validate(customer), api_token=token)


@router.get("/me", response_model=MeOut)
def me(customer: Customer = Depends(current_customer), session: Session = Depends(get_session)) -> MeOut:
    wallets = accounts.wallets(session, customer.id)
    return MeOut(
        customer=CustomerOut.model_validate(customer), wallets=[WalletOut.model_validate(w) for w in wallets]
    )


@router.get("/wallets", response_model=list[WalletOut])
def list_wallets(
    customer: Customer = Depends(current_customer), session: Session = Depends(get_session)
) -> list[WalletOut]:
    return [WalletOut.model_validate(w) for w in accounts.wallets(session, customer.id)]


@router.post("/wallets", status_code=201, response_model=WalletOut)
def open_wallet(
    body: OpenWalletIn,
    customer: Customer = Depends(current_customer),
    session: Session = Depends(get_session),
) -> WalletOut:
    return WalletOut.model_validate(accounts.open_wallet(session, customer, body.currency))


@router.get("/wallets/{account_id}/transactions", response_model=TransactionPage)
def transactions(
    account_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    customer: Customer = Depends(current_customer),
    session: Session = Depends(get_session),
) -> TransactionPage:
    wallet = accounts.owned_wallet(session, customer, account_id)
    rows = accounts.history(session, wallet.id, limit, offset)
    items = [
        TransactionOut(
            id=r.posting_id,
            entry_id=r.entry_id,
            kind=r.kind,
            memo=r.memo,
            amount_minor=r.amount_minor,
            currency=r.currency,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return TransactionPage(items=items, next_offset=offset + limit if len(items) == limit else None)
