"""Helpers shared by the tests."""

import os
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

STAFF_PASSWORD = os.environ.get("CAROB_SEED_STAFF_PASSWORD", "test-password")
ADMIN = "omar.aziz@carob.example"
SUPERVISOR = "nour.haddad@carob.example"
AGENT = "ziad.farah@carob.example"
OTHER_AGENT = "hala.mansour@carob.example"


@dataclass
class SignedUp:
    id: str
    email: str
    token: str
    wallets: dict[str, str]

    @property
    def headers(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}"}


def fund(session: Session, account_id: str, amount_minor: int, currency: str) -> None:
    from carob.ledger import Leg, house_account, post_entry

    clearing = house_account(session, "provider_clearing", currency)
    post_entry(
        session,
        "topup",
        [Leg(clearing.id, -amount_minor, currency), Leg(uuid.UUID(account_id), amount_minor, currency)],
        memo="Test funding",
    )


def staff_token(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/staff/login", json={"email": email, "password": STAFF_PASSWORD})
    assert response.status_code == 200, response.text
    return {"authorization": f"Bearer {response.json()['token']}"}


def assert_ledger_consistent(session: Session) -> None:
    unbalanced = session.execute(
        text(
            "SELECT entry_id, currency, sum(amount_minor) FROM postings GROUP BY 1, 2 HAVING sum(amount_minor) <> 0"
        )
    ).all()
    assert unbalanced == [], f"unbalanced entries: {unbalanced}"
    drift = session.execute(
        text(
            "SELECT a.id, a.balance_minor, coalesce(sum(p.amount_minor), 0) FROM accounts a "
            "LEFT JOIN postings p ON p.account_id = a.id GROUP BY a.id "
            "HAVING a.balance_minor <> coalesce(sum(p.amount_minor), 0)"
        )
    ).all()
    assert drift == [], f"cached balances differ from postings: {drift}"


def balance(client: TestClient, person: SignedUp, currency: str) -> int:
    wallets: list[dict[str, Any]] = client.get("/v1/wallets", headers=person.headers).json()
    return next(w["balance_minor"] for w in wallets if w["currency"] == currency)
