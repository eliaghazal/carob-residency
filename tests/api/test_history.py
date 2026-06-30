from fastapi.testclient import TestClient


def test_history_lists_newest_first_and_pages(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    alice, bob = signup("Alice", usd=100_000), signup("Bob")
    for amount in (1_000, 2_000, 3_000):
        client.post(
            "/v1/transfers",
            json={"from_account_id": alice.wallets["USD"], "to_email": bob.email, "amount_minor": amount},
            headers=alice.headers,
        )
    first = client.get(f"/v1/wallets/{bob.wallets['USD']}/transactions?limit=2", headers=bob.headers).json()
    assert [t["amount_minor"] for t in first["items"]] == [3_000, 2_000]
    assert first["next_offset"] == 2
    second = client.get(
        f"/v1/wallets/{bob.wallets['USD']}/transactions?limit=2&offset={first['next_offset']}",
        headers=bob.headers,
    ).json()
    assert [t["amount_minor"] for t in second["items"]] == [1_000]
    assert second["next_offset"] is None


def test_history_of_another_customer_is_refused(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    alice, mallory = signup("Alice"), signup("Mallory")
    response = client.get(f"/v1/wallets/{alice.wallets['USD']}/transactions", headers=mallory.headers)
    assert response.status_code == 403
