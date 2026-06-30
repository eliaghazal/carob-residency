"""Test setup. Tests need a Postgres database they may wipe:

    CAROB_DATABASE_URL=postgresql+psycopg://carob:carob@localhost:5432/carob_test pytest

`make test` starts one with Docker Compose. Every test starts from empty
tables plus the reference data (house accounts, rates, staff).
"""

import os
import uuid
from collections.abc import Iterator

os.environ.setdefault("CAROB_DATABASE_URL", "postgresql+psycopg://carob:carob@localhost:5432/carob_test")
os.environ.setdefault("CAROB_MAILER", "log")
os.environ.setdefault("CAROB_LOG_FORMAT", "text")
os.environ.setdefault("CAROB_SEED_STAFF_PASSWORD", "test-password")
os.environ.setdefault("CAROB_PAYSTUB_WEBHOOK_SECRET", "whsec_test")

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from carob.api.app import create_app
from carob.db import get_engine, session_factory, session_scope
from carob.paystub_client import PaymentIntent, get_paystub
from carob.seed import reference_data
from helpers import SignedUp, fund

ROOT = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture(scope="session", autouse=True)
def migrated() -> None:
    config = Config(os.path.join(ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(ROOT, "migrations"))
    with get_engine().begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_db(migrated: None) -> Iterator[None]:
    with get_engine().begin() as connection:
        tables = connection.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        ).scalars()
        connection.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    with session_scope() as session:
        reference_data(session)
    yield


@pytest.fixture
def db() -> Iterator[Session]:
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()


class FakePaystub:
    """Stands in for the Paystub client in API tests."""

    def __init__(self) -> None:
        self.intents: dict[str, PaymentIntent] = {}

    def create_payment_intent(
        self, amount_minor: int, currency: str, metadata: dict[str, str]
    ) -> PaymentIntent:
        intent_id = f"pi_{uuid.uuid4().hex[:24]}"
        intent = PaymentIntent(
            intent_id, "requires_payment", f"http://paystub.test/checkout/{intent_id}", amount_minor, currency
        )
        self.intents[intent_id] = intent
        return intent

    def get_payment_intent(self, intent_id: str) -> PaymentIntent:
        return self.intents[intent_id]


@pytest.fixture
def paystub() -> FakePaystub:
    return FakePaystub()


@pytest.fixture
def client(paystub: FakePaystub) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_paystub] = lambda: paystub
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def signup(client: TestClient):  # type: ignore[no-untyped-def]
    counter = iter(range(10_000))

    def make(name: str = "Test Customer", verified: bool = True, **balances: int) -> SignedUp:
        n = next(counter)
        email = f"customer{n}-{uuid.uuid4().hex[:6]}@example.com"
        response = client.post("/v1/signup", json={"full_name": name, "email": email})
        assert response.status_code == 201, response.text
        body = response.json()
        person = SignedUp(body["customer"]["id"], email, body["api_token"], {})
        for wallet in client.get("/v1/wallets", headers=person.headers).json():
            person.wallets[wallet["currency"]] = wallet["id"]
        with session_scope() as session:
            if verified:
                session.execute(
                    text("UPDATE customers SET kyc_status = 'verified' WHERE id = :id"), {"id": person.id}
                )
            for currency, amount in balances.items():
                fund(session, person.wallets[currency.upper()], amount, currency.upper())
        return person

    return make
