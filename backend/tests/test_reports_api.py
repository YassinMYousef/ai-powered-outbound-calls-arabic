"""KPI math and the /api/reports surface, on the in-memory SQLite schema."""
from datetime import UTC, datetime, timedelta

import pytest

from app.data.models import CallLog


def _call(
    *,
    status: str = "completed",
    outcome: str | None = None,
    attempt_number: int = 1,
    duration: int | None = None,
    days_ago: int = 0,
) -> CallLog:
    created = datetime.now(UTC) - timedelta(days=days_ago)
    return CallLog(
        customer_phone="+201000000000",
        status=status,
        outcome=outcome,
        attempt_number=attempt_number,
        duration_seconds=duration,
        created_at=created,
    )


def test_kpis_empty_db_is_all_zero(client) -> None:
    body = client.get("/api/reports/kpis").json()
    assert body == {"fcr_rate": 0.0, "completion_rate": 0.0, "average_handle_time": 0.0}


def test_kpis_math(client, db_session) -> None:
    db_session.add_all(
        [
            # First attempts: 2 resolved, 1 transferred, 1 no_answer → FCR 2/4.
            _call(outcome="resolved", duration=100),
            _call(outcome="resolved", duration=200),
            _call(outcome="transferred", duration=300),
            _call(status="no_answer"),
            # Retry (attempt 2) resolved — not FCR, but counts for completion/AHT.
            _call(outcome="resolved", attempt_number=2, duration=400),
            # Still in progress — must not affect any KPI.
            _call(status="in_progress"),
        ]
    )
    db_session.commit()

    body = client.get("/api/reports/kpis").json()
    assert body["fcr_rate"] == pytest.approx(2 / 4)
    # Completed with an outcome: resolved x3 + transferred → 3/4 AI-handled.
    assert body["completion_rate"] == pytest.approx(3 / 4)
    assert body["average_handle_time"] == pytest.approx((100 + 200 + 300 + 400) / 4)


def test_trends_groups_by_day_and_orders_oldest_first(client, db_session) -> None:
    db_session.add_all(
        [
            _call(outcome="resolved", duration=120, days_ago=2),
            _call(outcome="transferred", duration=60, days_ago=2),
            _call(outcome="resolved", duration=180, days_ago=1),
            # Outside the window — excluded.
            _call(outcome="resolved", duration=999, days_ago=30),
        ]
    )
    db_session.commit()

    body = client.get("/api/reports/trends", params={"days": 14}).json()
    assert [p["value"] for p in body["fcr"]] == [pytest.approx(0.5), pytest.approx(1.0)]
    assert [p["value"] for p in body["completion"]] == [pytest.approx(0.5), pytest.approx(1.0)]
    assert [p["value"] for p in body["aht"]] == [pytest.approx(90.0), pytest.approx(180.0)]
    assert body["fcr"][0]["date"] < body["fcr"][1]["date"]


def test_trends_rejects_out_of_range_days(client) -> None:
    assert client.get("/api/reports/trends", params={"days": 0}).status_code == 422
    assert client.get("/api/reports/trends", params={"days": 91}).status_code == 422


def test_fcr_report_generates_article(client, db_session) -> None:
    # Whole-day report window ends at last midnight, so only calls from prior days
    # (days_ago >= 1) land inside it.
    db_session.add_all(
        [
            _call(outcome="resolved", duration=120, days_ago=1),
            _call(outcome="resolved", duration=180, days_ago=2),
            _call(outcome="transferred", duration=60, days_ago=1),
            _call(status="no_answer", days_ago=1),
        ]
    )
    db_session.commit()

    body = client.get("/api/reports/fcr", params={"days": 7}).json()
    assert body["total_calls"] == 4
    assert body["resolved_first_attempt"] == 2
    assert body["fcr_rate"] == pytest.approx(2 / 4)
    assert body["completion_rate"] == pytest.approx(2 / 3)
    assert "First Call Resolutions" in body["report_markdown"]
    assert "تقرير حالات الحل" in body["report_markdown"]
    # Phone numbers are masked in the artifact.
    assert "+201000000000" not in body["report_markdown"]
    assert "****0000" in body["report_markdown"]


def test_fcr_report_is_idempotent_per_window(client, db_session) -> None:
    from app.data.models import FCRReport

    db_session.add(_call(outcome="resolved", duration=100, days_ago=1))
    db_session.commit()

    first = client.get("/api/reports/fcr", params={"days": 7}).json()
    second = client.get("/api/reports/fcr", params={"days": 7}).json()
    assert first["id"] == second["id"]
    assert db_session.query(FCRReport).count() == 1


def test_fcr_report_empty_window(client) -> None:
    body = client.get("/api/reports/fcr").json()
    assert body["total_calls"] == 0
    assert body["fcr_rate"] == 0.0
    assert "لا توجد حالات" in body["report_markdown"]


# --- Report-accuracy audit (requirements doc §5) ---------------------------


def test_accuracy_empty_is_zero(client) -> None:
    assert client.get("/api/reports/accuracy").json() == {
        "report_accuracy": 0.0,
        "audited_calls": 0,
    }


def test_audit_sample_excludes_outcomeless_and_audited(client, db_session) -> None:
    db_session.add_all([_call(outcome="resolved"), _call(outcome="transferred"), _call(status="no_answer")])
    db_session.commit()

    sample = client.get("/api/reports/audit/sample", params={"n": 10}).json()
    assert len(sample) == 2  # the no_answer call has no outcome → not sampleable
    assert all(c["outcome"] is not None for c in sample)

    client.post("/api/reports/audit", json={"call_id": sample[0]["id"], "audited_outcome": "resolved"})
    assert len(client.get("/api/reports/audit/sample", params={"n": 10}).json()) == 1


def test_report_accuracy_math(client, db_session) -> None:
    calls = [_call(outcome="resolved"), _call(outcome="resolved"), _call(outcome="transferred")]
    db_session.add_all(calls)
    db_session.commit()
    for c in calls:
        db_session.refresh(c)

    # agree, disagree, agree → 2/3 accurate.
    client.post("/api/reports/audit", json={"call_id": calls[0].id, "audited_outcome": "resolved"})
    client.post("/api/reports/audit", json={"call_id": calls[1].id, "audited_outcome": "unresolved"})
    client.post("/api/reports/audit", json={"call_id": calls[2].id, "audited_outcome": "transferred"})

    body = client.get("/api/reports/accuracy").json()
    assert body["audited_calls"] == 3
    assert body["report_accuracy"] == pytest.approx(2 / 3)


def test_submit_audit_is_idempotent_per_call(client, db_session) -> None:
    from app.data.models import CallAudit

    call = _call(outcome="resolved")
    db_session.add(call)
    db_session.commit()
    db_session.refresh(call)

    first = client.post("/api/reports/audit", json={"call_id": call.id, "audited_outcome": "resolved"}).json()
    assert first["is_accurate"] is True
    second = client.post("/api/reports/audit", json={"call_id": call.id, "audited_outcome": "unresolved"}).json()
    assert second["is_accurate"] is False
    assert first["id"] == second["id"]
    assert db_session.query(CallAudit).count() == 1


def test_submit_audit_unknown_call_is_404(client) -> None:
    resp = client.post("/api/reports/audit", json={"call_id": 999999, "audited_outcome": "resolved"})
    assert resp.status_code == 404
