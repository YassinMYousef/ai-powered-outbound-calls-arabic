"""Reporting endpoints — KPIs for the dashboard + the FCR report.

Module: Backend/Data & Reporting.
KPIs (requirements doc §5): FCR rate, AI call completion %, average handle time.
"""
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/kpis")
def get_kpis() -> dict:
    """Return {"fcr_rate": ..., "completion_rate": ..., "average_handle_time": ...}."""
    raise HTTPException(status_code=501, detail="Not implemented — see app/data/reporting.py")


@router.get("/fcr")
def get_fcr_report() -> dict:
    """Return the auto-generated 'First Call Resolutions' report for the quality team."""
    raise HTTPException(status_code=501, detail="Not implemented — see app/data/reporting.py")
