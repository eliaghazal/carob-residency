"""Client for Paystub, our card payment provider, and its webhook signatures.

Paystub signs each webhook: header `Paystub-Signature: t=<unix seconds>,v1=<hex>`
where v1 is HMAC-SHA256 over "<t>.<raw body>" with the endpoint's signing
secret. Docs: services/paystub/README.md (their sandbox, which we run locally).
"""

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

import httpx

from carob.config import get_settings
from carob.errors import ProviderError

SIGNATURE_TOLERANCE_SECONDS = 300


@dataclass(frozen=True)
class PaymentIntent:
    id: str
    status: str
    checkout_url: str
    amount: int
    currency: str


class PaystubClient:
    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self._http = httpx.Client(
            base_url=base_url, timeout=timeout, headers={"authorization": f"Bearer {api_key}"}
        )

    def create_payment_intent(
        self, amount_minor: int, currency: str, metadata: dict[str, str]
    ) -> PaymentIntent:
        try:
            response = self._http.post(
                "/v1/payment_intents",
                json={"amount": amount_minor, "currency": currency, "metadata": metadata},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError("could not create the payment at Paystub") from exc
        return _intent(response.json())

    def get_payment_intent(self, intent_id: str) -> PaymentIntent:
        try:
            response = self._http.get(f"/v1/payment_intents/{intent_id}")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError("could not read the payment at Paystub") from exc
        return _intent(response.json())


def _intent(body: dict[str, Any]) -> PaymentIntent:
    return PaymentIntent(
        id=body["id"],
        status=body["status"],
        checkout_url=body.get("checkout_url", ""),
        amount=int(body["amount"]),
        currency=body["currency"],
    )


def get_paystub() -> PaystubClient:
    s = get_settings()
    return PaystubClient(s.paystub_url, s.paystub_api_key, s.paystub_timeout_seconds)


def sign(body: bytes, secret: str, timestamp: int | None = None) -> str:
    t = int(time.time()) if timestamp is None else timestamp
    mac = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={t},v1={mac}"


def verify_signature(body: bytes, header: str | None, secret: str, now: float | None = None) -> bool:
    if not header:
        return False
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    try:
        t = int(parts["t"])
        given = parts["v1"]
    except (KeyError, ValueError):
        return False
    current = time.time() if now is None else now
    if abs(current - t) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, given)
