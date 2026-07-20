"""Reporting endpoints — KPIs for the dashboard + the FCR report.

Module: Backend/Data & Reporting.
KPIs (requirements doc §5): FCR rate, AI call completion %, average handle time.

TODO(auth): guard with data/auth.require_role("quality_manager") once OAuth2/RBAC
lands (Person D) — reporting data is internal.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.data import reporting
from app.data.db import get_db

router = APIRouter()


@router.get("/kpis")
def get_kpis(db: Session = Depends(get_db)) -> dict:
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
    days: int = Query(default=14, ge=1, le=90), db: Session = Depends(get_db)
) -> dict:
    """Per-day KPI series ({"fcr": [...], "completion": [...], "aht": [...]}) for
    the dashboard trend charts. Mirrors frontend/src/types/reports.ts::Trends."""
    return reporting.daily_trends(db, days)


@router.get("/fcr")
def get_fcr_report() -> dict:
    """Return the auto-generated 'First Call Resolutions' report for the quality team."""
    raise HTTPException(status_code=501, detail="Not implemented — see app/data/reporting.py")
