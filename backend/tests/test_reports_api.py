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


def test_fcr_report_still_stubbed(client) -> None:
    assert client.get("/api/reports/fcr").status_code == 501
