from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from helpers import assert_ledger_consistent, balance


def test_a_quote_applies_the_rate_and_the_spread(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup(usd=10_000)
    quote = client.post(
        "/v1/fx/quotes",
        json={"from_currency": "USD", "to_currency": "LBP", "from_minor": 10_000},
        headers=person.headers,
    )
    assert quote.status_code == 201, quote.text
    # 100.00 USD x 89,500 x (1 - 0.50%) = 8,905,250.00 LBP
    assert quote.json()["to_minor"] == 890_525_000


def test_a_conversion_moves_money_between_own_wallets(client: TestClient, signup, db: Session) -> None:  # type: ignore[no-untyped-def]
    person = signup(usd=10_000)
    response = client.post(
        "/v1/fx/conversions",
        json={
            "from_account_id": person.wallets["USD"],
            "to_account_id": person.wallets["LBP"],
            "from_minor": 4_000,
        },
        headers=person.headers,
    )
    assert response.status_code == 201, response.text
    assert balance(client, person, "USD") == 6_000
    assert balance(client, person, "LBP") > 350_000_000
    assert_ledger_consistent(db)


def test_cannot_convert_more_than_the_balance(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup(usd=1_000)
    response = client.post(
        "/v1/fx/conversions",
        json={
            "from_account_id": person.wallets["USD"],
            "to_account_id": person.wallets["LBP"],
            "from_minor": 2_000,
        },
        headers=person.headers,
    )
    assert response.status_code == 422
