import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from carob import transfers
from carob.api.deps import current_customer
from carob.api.schemas import TransferIn, TransferOut
from carob.db import get_session
from carob.errors import NotFound
from carob.metrics import TRANSFERS
from carob.models import Account, Customer, Transfer

router = APIRouter(prefix="/v1/transfers", tags=["transfers"])


@router.post("", status_code=201, response_model=TransferOut)
def send(
    body: TransferIn, customer: Customer = Depends(current_customer), session: Session = Depends(get_session)
) -> TransferOut:
    transfer = transfers.send(
        session, customer, body.from_account_id, body.to_email, body.amount_minor, body.note
    )
    TRANSFERS.labels(transfer.currency).inc()
    return TransferOut.model_validate(transfer)


@router.get("/{transfer_id}", response_model=TransferOut)
def get_transfer(
    transfer_id: uuid.UUID,
    customer: Customer = Depends(current_customer),
    session: Session = Depends(get_session),
) -> TransferOut:
    transfer = session.get(Transfer, transfer_id)
    if transfer is None:
        raise NotFound("transfer not found")
    owners = {
        session.get(Account, transfer.from_account_id).customer_id,  # type: ignore[union-attr]
        session.get(Account, transfer.to_account_id).customer_id,  # type: ignore[union-attr]
    }
    if customer.id not in owners:
        raise NotFound("transfer not found")
    return TransferOut.model_validate(transfer)
