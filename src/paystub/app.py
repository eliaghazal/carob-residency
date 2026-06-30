"""Paystub: the sandbox of Carob's card payment provider, run locally.

Carob does not own this service; treat it like a third party. It creates
payment intents, takes the card payment on a hosted checkout page, and
tells the merchant by webhook, at least once, retrying on any non-2xx
answer or a timeout (2 seconds). Merchant dashboard: /admin.
"""

import json
import logging
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from html import escape
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Form, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from paystub.signing import sign
from paystub.store import Store

log = logging.getLogger("paystub")
logging.basicConfig(
    level=logging.INFO, format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}'
)

API_KEY = os.environ.get("PAYSTUB_API_KEY", "sk_test_carob_dev")
ADMIN_TOKEN = os.environ.get("PAYSTUB_ADMIN_TOKEN", "paystub-admin-dev")
WEBHOOK_URL = os.environ.get("PAYSTUB_WEBHOOK_URL", "http://localhost:8000/webhooks/paystub")
PUBLIC_URL = os.environ.get("PAYSTUB_PUBLIC_URL", "http://localhost:8090")
DB_PATH = os.environ.get("PAYSTUB_DB", "paystub.sqlite3")
TEST_MODE = os.environ.get("PAYSTUB_TEST_MODE", "1") == "1"
# Retry delays in seconds; PAYSTUB_RETRY_SCALE shrinks them for tests (0.01 turns minutes into seconds).
RETRY_SCHEDULE = [10, 30, 120, 600, 1800, 3600]
RETRY_SCALE = float(os.environ.get("PAYSTUB_RETRY_SCALE", "1"))
DELIVERY_TIMEOUT = 2.0

store = Store(DB_PATH)
if store.setting("signing_secret") is None:
    store.set_setting("signing_secret", os.environ.get("PAYSTUB_WEBHOOK_SECRET", "whsec_dev_carob"))
    store.set_setting("secret_rotated_at", "never")


def require_key(authorization: str | None = Header(default=None)) -> None:
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="invalid API key")


def require_admin(authorization: str | None = Header(default=None)) -> None:
    if authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(status_code=401, detail="invalid admin token")


class IntentIn(BaseModel):
    amount: int = Field(gt=0)
    currency: str = Field(pattern="^[A-Z]{3}$")
    metadata: dict[str, str] = {}


class Chaos(BaseModel):
    duplicate_rate: float = Field(default=0.0, ge=0, le=1)
    delay_ms: int = Field(default=0, ge=0, le=30_000)


def _public_intent(intent: dict[str, Any]) -> dict[str, Any]:
    return {**intent, "checkout_url": f"{PUBLIC_URL}/checkout/{intent['id']}"}


def _emit(intent_id: str, event_type: str) -> None:
    intent = store.intent(intent_id)
    assert intent is not None
    event_id = f"evt_{secrets.token_hex(12)}"
    payload = {
        "id": event_id,
        "type": event_type,
        "created": int(time.time()),
        "data": _public_intent(intent),
    }
    store.add_event(event_id, event_type, json.dumps(payload, separators=(",", ":")))
    chaos = Chaos(**json.loads(store.setting("chaos") or "{}"))
    if chaos.duplicate_rate and secrets.randbelow(1000) < chaos.duplicate_rate * 1000:
        store.add_delivery(event_id)  # at-least-once: sometimes we really do send it twice


def _deliver_once(event_id: str, body: str) -> tuple[bool, str]:
    secret = store.setting("signing_secret") or ""
    chaos = Chaos(**json.loads(store.setting("chaos") or "{}"))
    if chaos.delay_ms:
        time.sleep(chaos.delay_ms / 1000)
    try:
        response = httpx.post(
            WEBHOOK_URL,
            content=body.encode(),
            headers={"content-type": "application/json", "paystub-signature": sign(body.encode(), secret)},
            timeout=DELIVERY_TIMEOUT,
        )
        return 200 <= response.status_code < 300, f"HTTP {response.status_code}"
    except httpx.HTTPError as exc:
        return False, type(exc).__name__


def _deliverer(stop: threading.Event) -> None:
    while not stop.is_set():
        for delivery in store.due_deliveries():
            ok, result = _deliver_once(delivery["event_id"], delivery["body"])
            attempt = delivery["attempts"] + 1
            if ok:
                store.finish_delivery(delivery["id"], "delivered", result, attempt)
            elif attempt > len(RETRY_SCHEDULE):
                store.finish_delivery(delivery["id"], "failed", result, attempt)
            else:
                store.retry_delivery(
                    delivery["id"], result, attempt, RETRY_SCHEDULE[attempt - 1] * RETRY_SCALE
                )
            log.info(f"webhook {delivery['event_id']} attempt {attempt}: {result}")
        stop.wait(0.2)


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    stop = threading.Event()
    thread = threading.Thread(target=_deliverer, args=(stop,), daemon=True)
    thread.start()
    yield
    stop.set()


app = FastAPI(title="Paystub sandbox", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/payment_intents", dependencies=[Depends(require_key)])
def create_intent(body: IntentIn) -> dict[str, Any]:
    intent = store.create_intent(body.amount, body.currency, body.metadata)
    return _public_intent(intent)


@app.get("/v1/payment_intents/{intent_id}", dependencies=[Depends(require_key)])
def get_intent(intent_id: str) -> dict[str, Any]:
    intent = store.intent(intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="no such payment intent")
    return _public_intent(intent)


def _settle(intent_id: str, outcome: str) -> dict[str, Any]:
    intent = store.intent(intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="no such payment intent")
    if intent["status"] != "requires_payment":
        return _public_intent(intent)
    store.set_intent_status(intent_id, outcome)
    _emit(intent_id, "payment.succeeded" if outcome == "succeeded" else "payment.failed")
    return _public_intent(store.intent(intent_id) or intent)


@app.post("/v1/test/payment_intents/{intent_id}/succeed", dependencies=[Depends(require_key)])
def test_succeed(intent_id: str) -> dict[str, Any]:
    """Sandbox only: pay without the checkout page (load tests, automated tests)."""
    if not TEST_MODE:
        raise HTTPException(status_code=404)
    return _settle(intent_id, "succeeded")


@app.post("/v1/test/payment_intents/{intent_id}/fail", dependencies=[Depends(require_key)])
def test_fail(intent_id: str) -> dict[str, Any]:
    if not TEST_MODE:
        raise HTTPException(status_code=404)
    return _settle(intent_id, "failed")


@app.get("/checkout/{intent_id}", response_class=HTMLResponse)
def checkout(intent_id: str) -> str:
    intent = store.intent(intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="no such payment intent")
    amount = f"{intent['amount'] / 100:,.2f} {escape(intent['currency'])}"
    if intent["status"] != "requires_payment":
        return f"<h1>Paystub sandbox</h1><p>This payment is {escape(intent['status'])}.</p>"
    return f"""<!doctype html><meta charset=utf-8><title>Paystub checkout</title>
<body style="font:16px system-ui;max-width:28rem;margin:4rem auto">
<h1>Paystub sandbox</h1><p>Pay <strong>{amount}</strong> to Carob.</p>
<form method=post action="/checkout/{escape(intent_id)}/pay"><button>Pay with test card 4242</button></form>
<form method=post action="/checkout/{escape(intent_id)}/decline"><button>Decline</button></form></body>"""


@app.post("/checkout/{intent_id}/pay")
def checkout_pay(intent_id: str) -> RedirectResponse:
    _settle(intent_id, "succeeded")
    return RedirectResponse(f"/checkout/{intent_id}", status_code=303)


@app.post("/checkout/{intent_id}/decline")
def checkout_decline(intent_id: str) -> RedirectResponse:
    _settle(intent_id, "failed")
    return RedirectResponse(f"/checkout/{intent_id}", status_code=303)


# Merchant dashboard (what Carob's team sees when they log in to Paystub).


@app.get("/admin/settings", dependencies=[Depends(require_admin)])
def admin_settings() -> dict[str, Any]:
    secret = store.setting("signing_secret") or ""
    return {
        "webhook_url": WEBHOOK_URL,
        "signing_secret_hint": secret[:9] + "..." + secret[-4:],
        "secret_rotated_at": store.setting("secret_rotated_at"),
        "chaos": json.loads(store.setting("chaos") or "{}"),
        "notices": json.loads(store.setting("notices") or "[]"),
    }


@app.get("/admin/settings/signing-secret", dependencies=[Depends(require_admin)])
def admin_reveal_secret() -> dict[str, str]:
    return {"signing_secret": store.setting("signing_secret") or ""}


@app.post("/admin/rotate-secret", dependencies=[Depends(require_admin)])
def admin_rotate(reason: str = Form(default="scheduled rotation")) -> dict[str, str]:
    secret = f"whsec_{secrets.token_urlsafe(24)}"
    store.set_setting("signing_secret", secret)
    rotated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    store.set_setting("secret_rotated_at", rotated)
    notices = json.loads(store.setting("notices") or "[]")
    notices.append(
        {"at": rotated, "text": f"Webhook signing secret rotated ({reason}). Update your endpoint."}
    )
    store.set_setting("notices", json.dumps(notices[-20:]))
    return {"rotated_at": rotated}


@app.put("/admin/chaos", dependencies=[Depends(require_admin)])
def admin_chaos(body: Chaos) -> dict[str, Any]:
    store.set_setting("chaos", body.model_dump_json())
    return body.model_dump()


@app.get("/admin/events", dependencies=[Depends(require_admin)])
def admin_events(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    return store.deliveries(status, limit)


@app.post("/admin/events/{event_id}/resend", dependencies=[Depends(require_admin)])
def admin_resend(event_id: str) -> dict[str, str]:
    if not store.add_delivery(event_id):
        raise HTTPException(status_code=404, detail="no such event")
    return {"queued": event_id}


@app.post("/admin/events/resend-failed", dependencies=[Depends(require_admin)])
def admin_resend_failed() -> dict[str, int]:
    return {"queued": store.requeue_failed()}
