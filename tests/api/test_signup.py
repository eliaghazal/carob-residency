from fastapi.testclient import TestClient


def test_signup_opens_usd_and_lbp_wallets(client: TestClient) -> None:
    response = client.post("/v1/signup", json={"full_name": "Lea Khoury", "email": "Lea@Example.com"})
    assert response.status_code == 201
    body = response.json()
    assert body["customer"]["email"] == "lea@example.com"
    assert body["api_token"].startswith("crb_")
    me = client.get("/v1/me", headers={"authorization": f"Bearer {body['api_token']}"}).json()
    assert sorted(w["currency"] for w in me["wallets"]) == ["LBP", "USD"]
    assert all(w["balance_minor"] == 0 for w in me["wallets"])


def test_the_same_email_cannot_sign_up_twice(client: TestClient) -> None:
    client.post("/v1/signup", json={"full_name": "Lea Khoury", "email": "lea@example.com"})
    again = client.post("/v1/signup", json={"full_name": "Lea K", "email": "LEA@example.com"})
    assert again.status_code == 409


def test_requests_without_a_valid_token_are_refused(client: TestClient) -> None:
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/me", headers={"authorization": "Bearer crb_nope"}).status_code == 401


def test_a_customer_can_open_a_euro_wallet_once(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup()
    assert client.post("/v1/wallets", json={"currency": "EUR"}, headers=person.headers).status_code == 201
    assert client.post("/v1/wallets", json={"currency": "EUR"}, headers=person.headers).status_code == 409
