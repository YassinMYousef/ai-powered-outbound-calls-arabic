"""KPI queries and the auto-generated "First Call Resolutions" report.

Module: Backend/Data & Reporting.
Targets (requirements doc §5): FCR rate ≥ 90%, time-to-answer < 2s for the
chatbot; AHT and completion % are compared against the live-agent baseline.

All queries run on both Postgres and SQLite (tests) — no dialect-specific SQL.
Rates are 0-1 fractions; an empty window yields 0.0, which the dashboard shows
as "below target" rather than pretending there is data.
"""
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.data.models import CallAudit, CallLog, FCRReport

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


def _mask_phone(phone: str) -> str:
    """Show only the last 4 digits in the report — PII stays out of the artifact."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"****{digits[-4:]}" if len(digits) >= 4 else "****"


def _pct(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def _window_metrics(db: Session, period_start: datetime, period_end: datetime) -> dict:
    """FCR/completion/AHT and counts over [period_start, period_end)."""
    window = (CallLog.created_at >= period_start, CallLog.created_at < period_end)
    first_terminal = _FIRST_ATTEMPT_DONE & CallLog.status.in_(TERMINAL_STATUSES)
    completed_with_outcome = _COMPLETED & CallLog.outcome.is_not(None)

    total_calls, total_first, resolved_first, completed_total, ai_handled = db.execute(
        select(
            func.count(CallLog.id),
            func.coalesce(func.sum(case((first_terminal, 1), else_=0)), 0),
            func.coalesce(func.sum(case((first_terminal & _RESOLVED_FIRST, 1), else_=0)), 0),
            func.coalesce(func.sum(case((completed_with_outcome, 1), else_=0)), 0),
            func.coalesce(
                func.sum(case((completed_with_outcome & (CallLog.outcome != "transferred"), 1), else_=0)),
                0,
            ),
        ).where(*window)
    ).one()

    mean_duration = db.execute(
        select(func.avg(CallLog.duration_seconds)).where(
            *window, _COMPLETED, CallLog.duration_seconds.is_not(None)
        )
    ).scalar_one()

    return {
        "total_calls": total_calls,
        "resolved_first_attempt": resolved_first,
        "fcr_rate": _ratio(resolved_first, total_first),
        "completion_rate": _ratio(ai_handled, completed_total),
        "average_handle_time_seconds": float(mean_duration) if mean_duration is not None else None,
    }


def _report_markdown(period_start: datetime, period_end: datetime, metrics: dict, resolved: list[CallLog]) -> str:
    """The Arabic 'First Call Resolutions' article the quality team reads."""
    aht = metrics["average_handle_time_seconds"]
    lines = [
        "# تقرير حالات الحل من أول مكالمة (First Call Resolutions)",
        "",
        f"**الفترة:** {period_start.date().isoformat()} — {period_end.date().isoformat()}",
        f"**إجمالي المكالمات:** {metrics['total_calls']}",
        f"**نسبة الحل من أول محاولة (FCR):** {_pct(metrics['fcr_rate'])}",
        f"**نسبة المكالمات المُنجَزة آليًا بالكامل:** {_pct(metrics['completion_rate'])}",
        f"**متوسط زمن المعالجة:** {aht:.0f} ثانية" if aht is not None else "**متوسط زمن المعالجة:** لا توجد بيانات",
        "",
        f"## الحالات التي تم حلها ({len(resolved)})",
        "",
    ]
    if resolved:
        lines.append("| التاريخ | رقم التذكرة | الهاتف | المدة (ث) |")
        lines.append("| --- | --- | --- | --- |")
        for call in resolved:
            lines.append(
                f"| {call.created_at.date().isoformat()} "
                f"| {call.ticket_id or '—'} "
                f"| {_mask_phone(call.customer_phone)} "
                f"| {call.duration_seconds if call.duration_seconds is not None else '—'} |"
            )
    else:
        lines.append("_لا توجد حالات تم حلها في هذه الفترة._")
    return "\n".join(lines)


def generate_fcr_report(
    db: Session,
    *,
    period_start: datetime,
    period_end: datetime,
    generated_by_user_id: int | None = None,
) -> FCRReport:
    """Compile resolved calls into the formatted 'First Call Resolutions' article.

    Idempotent per (period_start, period_end): re-running refreshes the existing
    row rather than duplicating it (the model's unique constraint on the period).
    Returns the persisted FCRReport.
    """
    if period_end <= period_start:
        raise ValueError("period_end must be after period_start")

    metrics = _window_metrics(db, period_start, period_end)
    resolved = db.execute(
        select(CallLog)
        .where(
            CallLog.created_at >= period_start,
            CallLog.created_at < period_end,
            CallLog.outcome == "resolved",
        )
        .order_by(CallLog.created_at)
    ).scalars().all()
    markdown = _report_markdown(period_start, period_end, metrics, resolved)

    report = db.execute(
        select(FCRReport).where(
            FCRReport.period_start == period_start, FCRReport.period_end == period_end
        )
    ).scalar_one_or_none()
    if report is None:
        report = FCRReport(period_start=period_start, period_end=period_end)
        db.add(report)
    report.total_calls = metrics["total_calls"]
    report.resolved_first_attempt = metrics["resolved_first_attempt"]
    report.fcr_rate = metrics["fcr_rate"]
    report.completion_rate = metrics["completion_rate"]
    report.average_handle_time_seconds = metrics["average_handle_time_seconds"]
    report.report_markdown = markdown
    report.generated_by_user_id = generated_by_user_id
    db.commit()
    db.refresh(report)
    return report


def resolved_calls_in_window(
    db: Session, period_start: datetime, period_end: datetime
) -> list[CallLog]:
    """The resolved calls backing a report's [period_start, period_end) window."""
    return db.execute(
        select(CallLog)
        .where(
            CallLog.created_at >= period_start,
            CallLog.created_at < period_end,
            CallLog.outcome == "resolved",
        )
        .order_by(CallLog.created_at)
    ).scalars().all()


def generate_recent_fcr_report(
    db: Session, days: int = 7, generated_by_user_id: int | None = None
) -> FCRReport:
    """Generate the FCR report for the `days` whole days ending at last midnight (UTC).

    Snapping to day boundaries keeps nightly regeneration idempotent — the same
    period maps to the same FCRReport row rather than a new one every run.
    """
    period_end = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    period_start = period_end - timedelta(days=days)
    return generate_fcr_report(
        db,
        period_start=period_start,
        period_end=period_end,
        generated_by_user_id=generated_by_user_id,
    )


# --- Report accuracy (manual QA audit of AI outcomes) ---------------------


def report_accuracy(db: Session) -> dict:
    """% of audited calls where the AI's recorded outcome matched the auditor.

    Backs requirements doc §5's 'Report Accuracy' metric. Returns
    {"report_accuracy": 0-1 float, "audited_calls": int}; 0.0 with no audits yet.
    """
    total, accurate = db.execute(
        select(
            func.count(CallAudit.id),
            func.coalesce(func.sum(case((CallAudit.is_accurate.is_(True), 1), else_=0)), 0),
        )
    ).one()
    return {"report_accuracy": _ratio(accurate, total), "audited_calls": total}


def sample_calls_for_audit(db: Session, n: int = 10) -> list[CallLog]:
    """A random sample of finished (outcome-bearing) calls not yet audited.

    RANDOM() ordering is portable across Postgres and SQLite; the anti-join on
    call_audits keeps the reviewer from re-auditing calls already covered.
    """
    return db.execute(
        select(CallLog)
        .outerjoin(CallAudit, CallAudit.call_log_id == CallLog.id)
        .where(CallLog.outcome.is_not(None), CallAudit.id.is_(None))
        .order_by(func.random())
        .limit(n)
    ).scalars().all()


def upsert_audit(
    db: Session,
    *,
    call: CallLog,
    audited_outcome: str,
    note: str | None = None,
    user_id: int | None = None,
) -> CallAudit:
    """Record (or correct) the QA verdict for `call`; one audit per call.

    is_accurate snapshots whether the AI's current outcome matched the auditor.
    """
    row = db.execute(
        select(CallAudit).where(CallAudit.call_log_id == call.id)
    ).scalar_one_or_none()
    if row is None:
        row = CallAudit(call_log_id=call.id)
        db.add(row)
    row.ai_outcome = call.outcome
    row.audited_outcome = audited_outcome
    row.is_accurate = call.outcome == audited_outcome
    row.note = note
    row.audited_by_user_id = user_id
    db.commit()
    db.refresh(row)
    return row


def report_dict(report: FCRReport) -> dict:
    """Serialize an FCRReport for the API / dashboard."""
    return {
        "id": report.id,
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "total_calls": report.total_calls,
        "resolved_first_attempt": report.resolved_first_attempt,
        "fcr_rate": report.fcr_rate,
        "completion_rate": report.completion_rate,
        "average_handle_time_seconds": report.average_handle_time_seconds,
        "report_markdown": report.report_markdown,
        "generated_at": report.created_at.isoformat() if report.created_at else None,
    }
