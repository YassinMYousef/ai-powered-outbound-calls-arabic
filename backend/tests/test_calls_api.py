import pytest

from app.api import calls
from app.data.models import CallLog

TEST_NUMBER = "+201091894094"  # the team's verified Twilio test number (see .env HUMAN_AGENT_NUMBER)


@pytest.fixture
def dialed(monkeypatch) -> list[int]:
    calls_ids: list[int] = []
    monkeypatch.setattr(calls, "_enqueue_dial", calls_ids.append)
    return calls_ids


@pytest.fixture
def scheduled(monkeypatch) -> list[None]:
    invocations: list[None] = []
    monkeypatch.setattr(calls, "_enqueue_schedule", lambda: invocations.append(None))
    return invocations


def test_create_call_persists_and_enqueues_dial(client, db_session, dialed) -> None:
    response = client.post("/api/calls", json={"customer_phone": TEST_NUMBER, "ticket_id": "TCK-1"})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["customer_phone"] == TEST_NUMBER

    row = db_session.get(CallLog, body["id"])
    assert row.customer_phone == TEST_NUMBER
    assert row.ticket_id == "TCK-1"
    assert dialed == [row.id]


def test_create_call_without_ticket_id(client, dialed) -> None:
    response = client.post("/api/calls", json={"customer_phone": TEST_NUMBER})
    assert response.status_code == 202
    assert response.json()["ticket_id"] is None


def test_create_call_requires_phone(client, dialed) -> None:
    response = client.post("/api/calls", json={"customer_phone": ""})
    assert response.status_code == 422
    assert dialed == []


def test_schedule_enqueues_batch(client, scheduled) -> None:
    response = client.post("/api/calls/schedule")
    assert response.status_code == 202
    assert scheduled == [None]


def test_get_call_returns_logged_fields(client, db_session) -> None:
    row = CallLog(customer_phone=TEST_NUMBER, ticket_id="TCK-2", status="completed", outcome="resolved")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    response = client.get(f"/api/calls/{row.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["outcome"] == "resolved"
    assert body["ticket_id"] == "TCK-2"


def test_get_call_missing_is_404(client) -> None:
    response = client.get("/api/calls/999999")
    assert response.status_code == 404
