import json
import logging

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from carob import payments
from carob.config import get_settings
from carob.db import get_session
from carob.metrics import WEBHOOKS
from carob.paystub_client import verify_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)


async def raw_body(request: Request) -> bytes:
    """The exact bytes Paystub signed. Read here so the handler itself can stay synchronous."""
    return await request.body()


@router.post("/paystub")
def paystub_webhook(
    body: bytes = Depends(raw_body),
    signature: str | None = Header(default=None, alias="paystub-signature"),
    session: Session = Depends(get_session),
) -> JSONResponse:
    # A sync handler runs in the threadpool: database work here must not block the event loop.
    if not verify_signature(body, signature, get_settings().paystub_webhook_secret):
        WEBHOOKS.labels("bad_signature").inc()
        log.warning("webhook signature mismatch")
        return JSONResponse(
            status_code=400, content={"error": {"code": "bad_signature", "message": "signature mismatch"}}
        )
    event = json.loads(body)
    result = payments.handle_paystub_event(session, event)
    WEBHOOKS.labels(result).inc()
    log.info(
        "webhook handled",
        extra={"fields": {"event_id": event.get("id"), "type": event.get("type"), "result": result}},
    )
    return JSONResponse(status_code=200, content={"result": result})
