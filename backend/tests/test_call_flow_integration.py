"""Full call-flow integration test (Person B Sprint 4): CRM flag -> schedule
-> dial -> status webhook -> persisted terminal state.

Exercises the real functions across api/customers.py, api/calls.py,
workers/tasks.py, and telephony/webhooks.py together, rather than each in
isolation like the rest of the suite.

Two things every test here has to work around, both because this is genuinely
new territory — no existing test drove schedule_follow_up_batch or the retry
branch of /telephony/status:

- workers/tasks.py opens its own SessionLocal() (not the FastAPI get_db
  dependency the `client`/`db_session` fixtures override), so `_worker_db`
  points SessionLocal at the same in-memory engine `db_session` uses —
  StaticPool keeps that engine's one connection alive, so both sides see the
  same committed rows.
- Both schedule_follow_up_batch and the /telephony/status retry branch
  enqueue place_outbound_call via Celery (.delay()/.apply_async()), which
  needs a live broker. `_run_tasks_eagerly` redirects both onto a direct,
  synchronous call — the same technique Celery's own task_always_eager uses —
  so nothing here touches Redis or risks dialing for real.
"""
from sqlalchemy.orm import sessionmaker

from app.data.models import CallLog
from app.telephony import client as telephony_client
from app.workers.tasks import place_outbound_call, schedule_follow_up_batch


def _worker_db(monkeypatch, db_session):
    test_session_local = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    monkeypatch.setattr("app.data.db.SessionLocal", test_session_local)


def _run_tasks_eagerly(monkeypatch):
    monkeypatch.setattr(place_outbound_call, "delay", lambda call_id: place_outbound_call(call_id))
    monkeypatch.setattr(
        place_outbound_call, "apply_async", lambda args=(), **kw: place_outbound_call(*args)
    )


def test_flag_schedule_dial_and_complete_call(client, db_session, monkeypatch) -> None:
    _worker_db(monkeypatch, db_session)
    _run_tasks_eagerly(monkeypatch)

    dialed_numbers: list[str] = []

    def fake_place_call(to_number: str, call_id: int) -> str:
        dialed_numbers.append(to_number)
        return "CAtest0000000000000000000000000042"

    monkeypatch.setattr(telephony_client, "place_call", fake_place_call)

    # 1. CRM: create + flag a customer (api/customers.py) — this is the
    #    "fetch list of customers flagged for follow-up" workflow step.
    customer = client.post(
        "/api/customers", json={"name": "Mona Ali", "phone": "+201091894094"}
    ).json()
    flagged = client.post(
        f"/api/customers/{customer['id']}/flag", json={"ticket_id": "TCK-INTEGRATION"}
    ).json()
    assert flagged["status"] == "queued"

    call_id = flagged["id"]
    row = db_session.get(CallLog, call_id)
    assert row.customer_id == customer["id"]
    assert row.status == "queued"

    # 2. Schedule: workers.tasks.schedule_follow_up_batch picks up every
    #    queued row and dials it (workers/tasks.py).
    schedule_follow_up_batch()

    assert dialed_numbers == ["+201091894094"]
    db_session.refresh(row)
    assert row.status == "initiated"
    assert row.provider_call_sid == "CAtest0000000000000000000000000042"
    assert row.started_at is not None

    # 3. Twilio's status webhook (telephony/webhooks.py) reports the call
    #    answered, then completed — the real HTTP handlers, via `client`.
    client.post(
        f"/telephony/status?call_id={call_id}",
        data={"CallSid": row.provider_call_sid, "CallStatus": "in-progress"},
    )
    final = client.post(
        f"/telephony/status?call_id={call_id}",
        data={"CallSid": row.provider_call_sid, "CallStatus": "completed", "CallDuration": "22"},
    )
    assert final.status_code == 204

    db_session.refresh(row)
    assert row.status == "completed"
    assert row.duration_seconds == 22
    assert row.completed_at is not None

    # 4. The customer's call history (api/customers.py) reflects the
    #    finished call — the loop closes back where it started.
    history = client.get(f"/api/customers/{customer['id']}").json()["call_history"]
    assert len(history) == 1
    assert history[0]["id"] == call_id
    assert history[0]["ticket_id"] == "TCK-INTEGRATION"
    assert history[0]["status"] == "completed"


def test_failed_call_is_retried_with_customer_id_preserved(client, db_session, monkeypatch) -> None:
    """should_retry (call_flow.py) + the retry branch in /telephony/status,
    driven end-to-end instead of unit-tested in isolation. Also guards the
    customer_id propagation bug fixed alongside this test — the retry row
    used to silently drop the CRM link."""
    _worker_db(monkeypatch, db_session)
    _run_tasks_eagerly(monkeypatch)

    dialed_numbers: list[str] = []
    monkeypatch.setattr(
        telephony_client,
        "place_call",
        lambda to_number, call_id: dialed_numbers.append(to_number) or f"CA{call_id:032d}",
    )

    customer = client.post("/api/customers", json={"name": "Ahmed", "phone": "+201000000099"}).json()
    flagged = client.post(f"/api/customers/{customer['id']}/flag", json={}).json()

    schedule_follow_up_batch()

    first_row = db_session.get(CallLog, flagged["id"])
    response = client.post(
        f"/telephony/status?call_id={first_row.id}",
        data={"CallSid": first_row.provider_call_sid, "CallStatus": "no-answer"},
    )
    assert response.status_code == 204

    db_session.refresh(first_row)
    assert first_row.status == "no_answer"

    retry_row = db_session.query(CallLog).filter(CallLog.parent_call_log_id == first_row.id).one()
    assert retry_row.attempt_number == 2
    assert retry_row.customer_id == customer["id"]
    # The retry branch's own apply_async already ran (eagerly, via the
    # monkeypatch), so the retry was dialed as part of the webhook call above.
    assert dialed_numbers == ["+201000000099", "+201000000099"]
    assert retry_row.status == "initiated"
