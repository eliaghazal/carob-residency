from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from carob import fx
from carob.api.deps import current_customer
from carob.api.schemas import ConversionIn, ConversionOut, QuoteIn, QuoteOut
from carob.db import get_session
from carob.models import Customer

router = APIRouter(prefix="/v1/fx", tags=["exchange"])


@router.post("/quotes", status_code=201, response_model=QuoteOut)
def create_quote(
    body: QuoteIn, customer: Customer = Depends(current_customer), session: Session = Depends(get_session)
) -> QuoteOut:
    return QuoteOut.model_validate(
        fx.quote(session, customer, body.from_currency, body.to_currency, body.from_minor)
    )


@router.post("/conversions", status_code=201, response_model=ConversionOut)
def convert(
    body: ConversionIn,
    customer: Customer = Depends(current_customer),
    session: Session = Depends(get_session),
) -> ConversionOut:
    conversion = fx.convert(
        session, customer, body.from_account_id, body.to_account_id, body.from_minor, body.quote_id
    )
    return ConversionOut.model_validate(conversion)
