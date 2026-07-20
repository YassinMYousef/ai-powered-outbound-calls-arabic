"""Outbound-call endpoints — schedule follow-up calls and inspect their outcomes.

Module: Telephony & Call Orchestration, persistence via Backend/Data.

TODO(auth): guard with data/auth.require_role once OAuth2/RBAC lands — this
dials real, billed calls and is currently unauthenticated, same gap noted in
api/chat.py and api/kb.py.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
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


@router.post("/schedule", status_code=202)
def schedule_follow_up_batch() -> dict:
    """Enqueue every CallLog row still sitting at status == 'queued'.

    Delegates to app/workers/tasks.py::schedule_follow_up_batch.
    """
    _enqueue_schedule()
    return {"detail": "batch enqueued"}


@router.get("/{call_id}")
def get_call(call_id: int, db: Session = Depends(get_db)) -> dict:
    """Return the logged outcome, duration, and transcript for one call."""
    call = db.get(CallLog, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="call not found")
    return {
        "id": call.id,
        "customer_phone": call.customer_phone,
        "ticket_id": call.ticket_id,
        "status": call.status,
        "outcome": call.outcome,
        "duration_seconds": call.duration_seconds,
        "transcript": call.transcript,
        "attempt_number": call.attempt_number,
        "provider_call_sid": call.provider_call_sid,
    }
