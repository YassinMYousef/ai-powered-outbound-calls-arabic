"""Reporting endpoints — KPIs for the dashboard + the FCR report.

Module: Backend/Data & Reporting.
KPIs (requirements doc §5): FCR rate, AI call completion %, average handle time.
Reporting data is internal — every route requires the quality_manager role.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.data import audit, pdf_report, reporting
from app.data.auth import require_role
from app.data.db import get_db
from app.data.models import CallLog, User

router = APIRouter()


class AuditSubmission(BaseModel):
    call_id: int = Field(ge=1)
    audited_outcome: str = Field(pattern="^(resolved|unresolved|transferred|unknown)$")
    note: str | None = Field(default=None, max_length=2000)


@router.get("/kpis")
def get_kpis(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("quality_manager")),
) -> dict:
    """Return {"fcr_rate": ..., "completion_rate": ..., "average_handle_time": ...}.

    Rates are 0-1 fractions; all values are 0.0 when no calls are logged yet.
    Mirrors frontend/src/types/reports.ts::Kpis.
    """
    return {
        "fcr_rate": reporting.fcr_rate(db),
        "completion_rate": reporting.completion_rate(db),
        "average_handle_time": reporting.average_handle_time(db),
    }


@router.get("/trends")
def get_trends(
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("quality_manager")),
) -> dict:
    """Per-day KPI series ({"fcr": [...], "completion": [...], "aht": [...]}) for
    the dashboard trend charts. Mirrors frontend/src/types/reports.ts::Trends."""
    return reporting.daily_trends(db, days)


@router.get("/fcr")
def get_fcr_report(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("quality_manager")),
) -> dict:
    """Generate and return the 'First Call Resolutions' report for the last `days`.

    Idempotent per whole-day window (reporting.generate_recent_fcr_report):
    calling it repeatedly refreshes the same FCRReport row rather than piling up
    duplicates. Returns the metrics plus the formatted Arabic article markdown.
    """
    report = reporting.generate_recent_fcr_report(db, days=days, generated_by_user_id=user.id)
    audit.record(
        db, user_id=user.id, action="report.fcr.generate", resource_type="fcr_report",
        resource_id=report.id, detail={"days": days},
    )
    return reporting.report_dict(report)


@router.get("/fcr.pdf")
def get_fcr_report_pdf(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("quality_manager")),
) -> Response:
    """The same 'First Call Resolutions' report as a branded, downloadable PDF.

    Generates/refreshes the report for the last `days` (idempotent per whole-day
    window, like GET /fcr), then renders it with the Arabic PDF template.
    """
    report = reporting.generate_recent_fcr_report(db, days=days, generated_by_user_id=user.id)
    resolved = reporting.resolved_calls_in_window(db, report.period_start, report.period_end)
    pdf_bytes = pdf_report.render_fcr_pdf(report, resolved)
    audit.record(
        db, user_id=user.id, action="report.fcr.download_pdf", resource_type="fcr_report",
        resource_id=report.id, detail={"days": days},
    )
    filename = f"fcr-report-{report.period_start.date().isoformat()}_{report.period_end.date().isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Report accuracy: manual QA audit of AI outcomes (requirements doc §5) ---


@router.get("/accuracy")
def get_report_accuracy(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("quality_manager")),
) -> dict:
    """Return {"report_accuracy": 0-1, "audited_calls": n} — AI-vs-auditor agreement."""
    return reporting.report_accuracy(db)


@router.get("/audit/sample")
def get_audit_sample(
    n: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("quality_manager")),
) -> list[dict]:
    """A random sample of finished calls not yet audited, for manual review."""
    calls = reporting.sample_calls_for_audit(db, n)
    return [
        {
            "id": c.id,
            "ticket_id": c.ticket_id,
            "outcome": c.outcome,
            "status": c.status,
            "duration_seconds": c.duration_seconds,
            "transcript": c.transcript,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in calls
    ]


@router.post("/audit", status_code=201)
def submit_audit(
    body: AuditSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("quality_manager")),
) -> dict:
    """Record a QA auditor's true-outcome verdict for one call (idempotent per call)."""
    call = db.get(CallLog, body.call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="call not found")
    row = reporting.upsert_audit(
        db, call=call, audited_outcome=body.audited_outcome, note=body.note, user_id=user.id
    )
    audit.record(
        db, user_id=user.id, action="report.audit.submit", resource_type="call_log",
        resource_id=call.id,
        detail={"audited_outcome": row.audited_outcome, "is_accurate": row.is_accurate},
    )
    return {
        "id": row.id,
        "call_id": call.id,
        "ai_outcome": row.ai_outcome,
        "audited_outcome": row.audited_outcome,
        "is_accurate": row.is_accurate,
    }
