import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from carob.paystub_client import sign
from helpers import assert_ledger_consistent, balance

SECRET = "whsec_test"


def deliver(client: TestClient, event: dict, secret: str = SECRET):  # type: ignore[no-untyped-def]
    body = json.dumps(event).encode()
    return client.post(
        "/webhooks/paystub",
        content=body,
        headers={"paystub-signature": sign(body, secret), "content-type": "application/json"},
    )


def succeeded(event_id: str, intent_id: str, amount: int, currency: str = "USD") -> dict:  # type: ignore[type-arg]
    return {
        "id": event_id,
        "type": "payment.succeeded",
        "data": {"id": intent_id, "amount": amount, "currency": currency},
    }


def test_a_paid_topup_credits_the_wallet(client: TestClient, signup, db: Session) -> None:  # type: ignore[no-untyped-def]
    person = signup()
    topup = client.post(
        "/v1/topups",
        json={"account_id": person.wallets["USD"], "amount_minor": 2_500},
        headers=person.headers,
    )
    assert topup.status_code == 201, topup.text
    intent_id = topup.json()["checkout_url"].rsplit("/", 1)[1]
    assert deliver(client, succeeded("evt_1", intent_id, 2_500)).json() == {"result": "credited"}
    assert balance(client, person, "USD") == 2_500
    assert (
        client.get(f"/v1/topups/{topup.json()['id']}", headers=person.headers).json()["status"] == "succeeded"
    )
    assert_ledger_consistent(db)


def test_a_repeated_delivery_is_not_credited_again(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup()
    topup = client.post(
        "/v1/topups",
        json={"account_id": person.wallets["USD"], "amount_minor": 1_000},
        headers=person.headers,
    )
    intent_id = topup.json()["checkout_url"].rsplit("/", 1)[1]
    deliver(client, succeeded("evt_1", intent_id, 1_000))
    assert deliver(client, succeeded("evt_1", intent_id, 1_000)).json() == {"result": "duplicate"}
    assert balance(client, person, "USD") == 1_000


def test_a_bad_signature_is_refused(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup()
    topup = client.post(
        "/v1/topups",
        json={"account_id": person.wallets["USD"], "amount_minor": 1_000},
        headers=person.headers,
    )
    intent_id = topup.json()["checkout_url"].rsplit("/", 1)[1]
    assert deliver(client, succeeded("evt_1", intent_id, 1_000), secret="whsec_wrong").status_code == 400
    assert balance(client, person, "USD") == 0


def test_a_failed_payment_marks_the_topup_failed(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup()
    topup = client.post(
        "/v1/topups",
        json={"account_id": person.wallets["LBP"], "amount_minor": 500_000},
        headers=person.headers,
    )
    intent_id = topup.json()["checkout_url"].rsplit("/", 1)[1]
    event = {
        "id": "evt_2",
        "type": "payment.failed",
        "data": {"id": intent_id, "amount": 500_000, "currency": "LBP"},
    }
    assert deliver(client, event).json() == {"result": "failed"}
    assert client.get(f"/v1/topups/{topup.json()['id']}", headers=person.headers).json()["status"] == "failed"


def test_topup_limits(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup()
    too_big = client.post(
        "/v1/topups",
        json={"account_id": person.wallets["USD"], "amount_minor": 500_001},
        headers=person.headers,
    )
    assert too_big.status_code == 422
