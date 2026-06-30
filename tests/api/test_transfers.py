from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from helpers import assert_ledger_consistent, balance


def test_a_transfer_moves_money_and_charges_the_fee(client: TestClient, signup, db: Session) -> None:  # type: ignore[no-untyped-def]
    alice = signup("Alice", usd=50_000)
    bob = signup("Bob")
    response = client.post(
        "/v1/transfers",
        json={
            "from_account_id": alice.wallets["USD"],
            "to_email": bob.email,
            "amount_minor": 20_000,
            "note": "rent",
        },
        headers=alice.headers,
    )
    assert response.status_code == 201, response.text
    transfer = response.json()
    assert transfer["fee_minor"] == 50
    assert balance(client, alice, "USD") == 50_000 - 20_000 - 50
    assert balance(client, bob, "USD") == 20_000
    assert_ledger_consistent(db)


def test_small_transfers_are_free(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    alice, bob = signup("Alice", usd=5_000), signup("Bob")
    response = client.post(
        "/v1/transfers",
        json={"from_account_id": alice.wallets["USD"], "to_email": bob.email, "amount_minor": 1_500},
        headers=alice.headers,
    )
    assert response.json()["fee_minor"] == 0


def test_cannot_send_more_than_the_balance(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    alice, bob = signup("Alice", usd=1_000), signup("Bob")
    response = client.post(
        "/v1/transfers",
        json={"from_account_id": alice.wallets["USD"], "to_email": bob.email, "amount_minor": 1_001},
        headers=alice.headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "insufficient_funds"


def test_unverified_customers_cannot_send(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    alice, bob = signup("Alice", verified=False, usd=10_000), signup("Bob")
    response = client.post(
        "/v1/transfers",
        json={"from_account_id": alice.wallets["USD"], "to_email": bob.email, "amount_minor": 500},
        headers=alice.headers,
    )
    assert response.status_code == 403


def test_cannot_spend_from_someone_elses_wallet(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    alice, mallory = signup("Alice", usd=10_000), signup("Mallory")
    response = client.post(
        "/v1/transfers",
        json={"from_account_id": alice.wallets["USD"], "to_email": mallory.email, "amount_minor": 500},
        headers=mallory.headers,
    )
    assert response.status_code == 403
