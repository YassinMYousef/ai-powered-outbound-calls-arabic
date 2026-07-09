"""Outbound-call endpoints — schedule follow-up calls and inspect their outcomes.

Module: Telephony & Call Orchestration, persistence via Backend/Data.
"""
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/schedule", status_code=202)
def schedule_follow_up_batch() -> dict:
    """Fetch customers flagged for follow-up and enqueue outbound calls.

    Delegates to app/workers/tasks.py::schedule_follow_up_batch.
    """
    raise HTTPException(status_code=501, detail="Not implemented — see app/workers/tasks.py")


@router.get("/{call_id}")
def get_call(call_id: int) -> dict:
    """Return the logged outcome, duration, and transcript for one call."""
    raise HTTPException(status_code=501, detail="Not implemented")
