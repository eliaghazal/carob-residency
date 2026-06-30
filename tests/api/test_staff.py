from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from helpers import AGENT, SUPERVISOR, assert_ledger_consistent, balance, staff_token


def test_wrong_password_is_refused(client: TestClient) -> None:
    response = client.post("/staff/login", json={"email": AGENT, "password": "nope"})
    assert response.status_code == 401


def test_a_supervisor_can_reverse_a_transfer(client: TestClient, signup, db: Session) -> None:  # type: ignore[no-untyped-def]
    alice, bob = signup("Alice", usd=50_000), signup("Bob")
    transfer = client.post(
        "/v1/transfers",
        json={"from_account_id": alice.wallets["USD"], "to_email": bob.email, "amount_minor": 20_000},
        headers=alice.headers,
    ).json()
    agent, supervisor = staff_token(client, AGENT), staff_token(client, SUPERVISOR)
    assert (
        client.post(
            f"/staff/transfers/{transfer['id']}/reverse", json={"reason": "fraud"}, headers=agent
        ).status_code
        == 403
    )
    response = client.post(
        f"/staff/transfers/{transfer['id']}/reverse", json={"reason": "sent by mistake"}, headers=supervisor
    )
    assert response.status_code == 200
    assert response.json()["status"] == "reversed"
    assert balance(client, alice, "USD") == 50_000
    assert balance(client, bob, "USD") == 0
    again = client.post(
        f"/staff/transfers/{transfer['id']}/reverse", json={"reason": "again"}, headers=supervisor
    )
    assert again.status_code == 409
    assert_ledger_consistent(db)
