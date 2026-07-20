"""Outbound-call endpoints — schedule follow-up calls and inspect their outcomes.

Module: Telephony & Call Orchestration, persistence via Backend/Data.

TODO(auth): guard with data/auth.require_role once OAuth2/RBAC lands — this
dials real, billed calls and is currently unauthenticated, same gap noted in
api/chat.py and api/kb.py.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.data.models import CallLog

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateCallRequest(BaseModel):
    customer_phone: str = Field(min_length=1)  # E.164, e.g. "+201091894094"
    ticket_id: str | None = None


def _enqueue_dial(call_id: int) -> None:
    """Best-effort immediate dial — mirrors api/kb.py's _enqueue_ingest.

    retry=False so a dead broker fails fast instead of blocking the request;
    the row stays "queued" and schedule_follow_up_batch will pick it up later.
    """
    from app.workers.tasks import place_outbound_call

    try:
        place_outbound_call.apply_async(args=[call_id], retry=False)
    except Exception:
        logger.warning("could not enqueue dial for call %s (is Redis/the worker up?)", call_id)


def _enqueue_schedule() -> None:
    from app.workers.tasks import schedule_follow_up_batch

    try:
        schedule_follow_up_batch.apply_async(retry=False)
    except Exception:
        logger.warning("could not enqueue schedule_follow_up_batch (is Redis/the worker up?)")


def _call_dict(call: CallLog) -> dict:
    return {
        "id": call.id,
        "customer_id": call.customer_id,
        "customer_phone": call.customer_phone,
        "ticket_id": call.ticket_id,
        "status": call.status,
        "outcome": call.outcome,
        "duration_seconds": call.duration_seconds,
        "transcript": call.transcript,
        "attempt_number": call.attempt_number,
        "provider_call_sid": call.provider_call_sid,
        "created_at": call.created_at.isoformat(),
    }


@router.post("", status_code=202)
def create_call(body: CreateCallRequest, db: Session = Depends(get_db)) -> dict:
    """Log one customer for an outbound call and dial it now.

    This dials a real number and bills the configured Twilio account
    (telephony.client.place_call) — never call it with a number you don't
    have consent to call.
    """
    call = CallLog(customer_phone=body.customer_phone, ticket_id=body.ticket_id, status="queued")
    db.add(call)
    db.commit()
    db.refresh(call)
    _enqueue_dial(call.id)
    return {"id": call.id, "customer_phone": call.customer_phone, "ticket_id": call.ticket_id, "status": call.status}


@router.get("")
def list_calls(db: Session = Depends(get_db)) -> list[dict]:
    """List every CallLog row, newest first — the agent's Call Queue."""
    calls = db.execute(select(CallLog).order_by(CallLog.created_at.desc(), CallLog.id.desc())).scalars().all()
    return [_call_dict(c) for c in calls]


@router.post("/schedule", status_code=202)
def schedule_follow_up_batch() -> dict:
    """Enqueue every CallLog row still sitting at status == 'queued'.

    Delegates to app/workers/tasks.py::schedule_follow_up_batch.
    """
    _enqueue_schedule()
    return {"detail": "batch enqueued"}


@router.post("/{call_id}/dial", status_code=202)
def dial_call(call_id: int, db: Session = Depends(get_db)) -> dict:
    """Dial one existing queued row now — the Call Queue's per-row "Start call".

    This dials a real number and bills the configured Twilio account — only
    valid while the row is still "queued" (not yet dialed, not a terminal
    outcome); retries are handled automatically by telephony/webhooks.py's
    /status handler, not by re-dialing a finished row through here.
    """
    call = db.get(CallLog, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="call not found")
    if call.status != "queued":
        raise HTTPException(status_code=409, detail=f"call {call_id} is not queued (status={call.status})")
    _enqueue_dial(call.id)
    return {"id": call.id, "status": call.status}


@router.get("/{call_id}")
def get_call(call_id: int, db: Session = Depends(get_db)) -> dict:
    """Return the logged outcome, duration, and transcript for one call."""
    call = db.get(CallLog, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="call not found")
    return _call_dict(call)
