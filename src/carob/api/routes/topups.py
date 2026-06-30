import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from carob import payments
from carob.accounts import owned_wallet
from carob.api.deps import current_customer
from carob.api.schemas import TopupIn, TopupOut
from carob.db import get_session
from carob.errors import NotFound
from carob.models import Customer, Topup
from carob.paystub_client import PaystubClient, get_paystub

router = APIRouter(prefix="/v1/topups", tags=["topups"])


@router.post("", status_code=201, response_model=TopupOut)
def start_topup(
    body: TopupIn,
    customer: Customer = Depends(current_customer),
    session: Session = Depends(get_session),
    paystub: PaystubClient = Depends(get_paystub),
) -> TopupOut:
    topup = payments.start_topup(session, paystub, customer, body.account_id, body.amount_minor)
    return TopupOut.model_validate(topup)


@router.get("/{topup_id}", response_model=TopupOut)
def get_topup(
    topup_id: uuid.UUID,
    customer: Customer = Depends(current_customer),
    session: Session = Depends(get_session),
) -> TopupOut:
    topup = session.get(Topup, topup_id)
    if topup is None:
        raise NotFound("top-up not found")
    owned_wallet(session, customer, topup.account_id)
    return TopupOut.model_validate(topup)
