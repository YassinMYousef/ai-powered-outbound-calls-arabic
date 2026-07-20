"""KPI queries and the auto-generated "First Call Resolutions" report.

Module: Backend/Data & Reporting.
Targets (requirements doc §5): FCR rate ≥ 90%, time-to-answer < 2s for the
chatbot; AHT and completion % are compared against the live-agent baseline.

All queries run on both Postgres and SQLite (tests) — no dialect-specific SQL.
Rates are 0-1 fractions; an empty window yields 0.0, which the dashboard shows
as "below target" rather than pretending there is data.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.data.models import CallLog

# A call whose provider lifecycle is over — anything still queued/ringing/in
# progress has no outcome yet and must not drag a rate down.
TERMINAL_STATUSES = ("completed", "no_answer", "busy", "failed", "cancelled")

_FIRST_ATTEMPT_DONE = CallLog.attempt_number == 1
_RESOLVED_FIRST = (CallLog.attempt_number == 1) & (CallLog.outcome == "resolved")
_COMPLETED = CallLog.status == "completed"
# "Fully handled by the AI" = the call finished and never went to a human.
_AI_HANDLED = _COMPLETED & (CallLog.outcome != "transferred") & CallLog.outcome.is_not(None)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def fcr_rate(db: Session) -> float:
    """% of follow-up calls resolved on the first outbound attempt."""
    total, resolved = db.execute(
        select(
            func.count(CallLog.id),
            func.coalesce(func.sum(case((CallLog.outcome == "resolved", 1), else_=0)), 0),
        ).where(_FIRST_ATTEMPT_DONE, CallLog.status.in_(TERMINAL_STATUSES))
    ).one()
    return _ratio(resolved, total)


def completion_rate(db: Session) -> float:
    """% of calls fully handled by the AI without human handoff."""
    total, ai_handled = db.execute(
        select(
            func.count(CallLog.id),
            func.coalesce(func.sum(case((CallLog.outcome != "transferred", 1), else_=0)), 0),
        ).where(_COMPLETED, CallLog.outcome.is_not(None))
    ).one()
    return _ratio(ai_handled, total)


def average_handle_time(db: Session) -> float:
    """Mean call duration in seconds over completed calls (0.0 with no data)."""
    mean = db.execute(
        select(func.avg(CallLog.duration_seconds)).where(
            _COMPLETED, CallLog.duration_seconds.is_not(None)
        )
    ).scalar_one()
    return float(mean) if mean is not None else 0.0


def daily_trends(db: Session, days: int = 14) -> dict[str, list[dict]]:
    """Per-day KPI series for the dashboard trend charts.

    Returns {"fcr": [...], "completion": [...], "aht": [...]}, each a list of
    {"date": "YYYY-MM-DD", "value": float} ordered oldest→newest. Days with no
    calls are simply absent — the chart plots what exists.
    """
    since = datetime.now(UTC) - timedelta(days=days)
    day = func.date(CallLog.created_at)

    first_terminal = _FIRST_ATTEMPT_DONE & CallLog.status.in_(TERMINAL_STATUSES)
    completed_with_outcome = _COMPLETED & CallLog.outcome.is_not(None)

    rows = db.execute(
        select(
            day.label("day"),
            func.sum(case((first_terminal & (CallLog.outcome == "resolved"), 1), else_=0)),
            func.sum(case((first_terminal, 1), else_=0)),
            func.sum(case((completed_with_outcome & (CallLog.outcome != "transferred"), 1), else_=0)),
            func.sum(case((completed_with_outcome, 1), else_=0)),
            # AVG skips NULLs, so non-completed rows are excluded via CASE→NULL.
            func.avg(case((_COMPLETED, CallLog.duration_seconds))),
        )
        .where(CallLog.created_at >= since)
        .group_by(day)
        .order_by(day)
    ).all()

    fcr, completion, aht = [], [], []
    for row_day, resolved, first_total, ai_handled, completed_total, mean_duration in rows:
        date = str(row_day)  # SQLite returns str, Postgres a date object
        if first_total:
            fcr.append({"date": date, "value": _ratio(resolved, first_total)})
        if completed_total:
            completion.append({"date": date, "value": _ratio(ai_handled, completed_total)})
        if mean_duration is not None:
            aht.append({"date": date, "value": float(mean_duration)})
    return {"fcr": fcr, "completion": completion, "aht": aht}


def generate_fcr_report(db: Session) -> str:
    """Compile resolved calls into the formatted 'First Call Resolutions'
    article for the quality team."""
    raise NotImplementedError
