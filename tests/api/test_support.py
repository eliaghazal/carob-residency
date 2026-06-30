from fastapi.testclient import TestClient

from helpers import AGENT, OTHER_AGENT, SUPERVISOR, staff_token


def test_a_message_opens_a_conversation_in_a_queue(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup()
    response = client.post(
        "/v1/support/messages",
        json={"body": "I sent money but the transfer to the recipient failed"},
        headers=person.headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["conversation"]["queue"] == "transfers"


def test_low_confidence_messages_go_to_triage(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup()
    response = client.post("/v1/support/messages", json={"body": "hello?"}, headers=person.headers)
    assert response.json()["conversation"]["queue"] == "triage"


def test_follow_up_messages_join_the_open_conversation(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup()
    first = client.post(
        "/v1/support/messages", json={"body": "my card PIN is blocked at the ATM"}, headers=person.headers
    )
    second = client.post("/v1/support/messages", json={"body": "still blocked"}, headers=person.headers)
    assert first.json()["conversation"]["id"] == second.json()["conversation"]["id"]


def test_staff_reply_records_the_first_response(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup()
    conversation = client.post(
        "/v1/support/messages", json={"body": "my card PIN is blocked at the ATM"}, headers=person.headers
    ).json()["conversation"]
    agent = staff_token(client, AGENT)
    assert client.get("/staff/queues", headers=agent).json() == [
        {"queue": "cards", "waiting": 1, "breaching": 0}
    ]
    reply = client.post(
        f"/staff/conversations/{conversation['id']}/reply", json={"body": "Unblocked."}, headers=agent
    )
    assert reply.status_code == 201
    detail = client.get(f"/staff/conversations/{conversation['id']}", headers=agent).json()
    assert detail["conversation"]["first_response_at"] is not None
    assert [m["author_type"] for m in detail["messages"]] == ["customer", "staff"]


def test_agents_see_only_customers_they_are_helping(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup()
    conversation = client.post(
        "/v1/support/messages", json={"body": "my card PIN is blocked at the ATM"}, headers=person.headers
    ).json()["conversation"]
    agent, other = staff_token(client, AGENT), staff_token(client, OTHER_AGENT)
    assert client.get(f"/staff/customers/{person.id}", headers=agent).status_code == 403
    client.post(f"/staff/conversations/{conversation['id']}/assign", json={}, headers=agent)
    assert client.get(f"/staff/customers/{person.id}", headers=agent).status_code == 200
    assert client.get(f"/staff/customers/{person.id}", headers=other).status_code == 403
    assert (
        client.get(f"/staff/customers/{person.id}", headers=staff_token(client, SUPERVISOR)).status_code
        == 200
    )


def test_only_supervisors_decide_kyc(client: TestClient, signup) -> None:  # type: ignore[no-untyped-def]
    person = signup(verified=False)
    agent, supervisor = staff_token(client, AGENT), staff_token(client, SUPERVISOR)
    assert (
        client.post(
            f"/staff/customers/{person.id}/kyc", json={"status": "verified"}, headers=agent
        ).status_code
        == 403
    )
    response = client.post(
        f"/staff/customers/{person.id}/kyc", json={"status": "verified"}, headers=supervisor
    )
    assert response.json()["kyc_status"] == "verified"
