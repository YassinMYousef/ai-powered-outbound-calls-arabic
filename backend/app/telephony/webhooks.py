"""Telephony provider webhook endpoints — the live half of the call loop.

Module: Telephony & Call Orchestration.
The provider POSTs here during a call; handlers must respond quickly (TwiML)
and be idempotent, because the provider retries on timeout.
"""
import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse

from app.data.db import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

# Placeholder greeting. Real dynamic Arabic goes through speech.tts.synthesize
# and is served to Twilio as <Play>; <Say> only covers this static smoke-test line.
GREETING_AR = "مرحبًا بك. هذه مكالمة متابعة للتأكد من أن مشكلتك قد تم حلها."

# Polly.Zeina is Modern Standard Arabic (language code "arb"); Twilio has no
# Egyptian-dialect voice.
_AR_VOICE = "Polly.Zeina"
_AR_LANG = "arb"


def _twiml(response: VoiceResponse) -> Response:
    return Response(content=str(response), media_type="application/xml")


@router.post("/voice")
async def voice(request: Request) -> Response:
    """Call answered → play the dynamic Arabic greeting (speech.tts), then gather speech."""
    response = VoiceResponse()
    response.say(GREETING_AR, voice=_AR_VOICE, language=_AR_LANG)
    return _twiml(response)


@router.post("/gather")
async def gather(request: Request):
    """Customer speech received → speech.stt → conversation.dialog decides the next
    action → speech.tts reply, or transfer to a human agent (call_flow)."""
    raise NotImplementedError


@router.post("/status")
async def status(request: Request, db: Session = Depends(get_db)) -> Response:
    """Final call status (completed / no-answer / failed) → log outcome, maybe retry."""
    form = await request.form()
    call_sid = form.get("CallSid")
    twilio_status = form.get("CallStatus")
    duration = form.get("CallDuration")
    call_id = request.query_params.get("call_id")

    logger.info(
        "call finished: sid=%s status=%s duration=%ss call_id=%s",
        call_sid, twilio_status, duration, call_id,
    )

    if not call_id:
        logger.warning("status webhook: no call_id in query params, cannot persist")
        return Response(status_code=204)

    # place_call subscribes to status_callback_event=["initiated", "ringing",
    # "answered", "completed"], so this webhook fires multiple times per call,
    # not just at the end. Twilio's "answered" event carries CallStatus=
    # "in-progress". Only the terminal map entries end the call and are
    # eligible for retry; anything else just tracks progress.
    _TERMINAL_STATUS_MAP = {
        "completed": "completed",
        "busy": "busy",
        "failed": "failed",
        "no-answer": "no_answer",
        "canceled": "cancelled",
    }
    _INTERMEDIATE_STATUS_MAP = {
        "initiated": "initiated",
        "ringing": "ringing",
        "in-progress": "in_progress",
    }

    is_terminal = twilio_status in _TERMINAL_STATUS_MAP
    our_status = _TERMINAL_STATUS_MAP.get(twilio_status) or _INTERMEDIATE_STATUS_MAP.get(twilio_status)
    if our_status is None:
        logger.warning("status webhook: unrecognized CallStatus=%s, ignoring", twilio_status)
        return Response(status_code=204)

    from datetime import UTC, datetime

    from app.data.models import CallLog
    from app.telephony.call_flow import should_retry
    from app.workers.tasks import place_outbound_call

    row = db.get(CallLog, int(call_id))
    if row is None:
        logger.error("status webhook: no CallLog row with id=%s", call_id)
        return Response(status_code=204)

    row.status = our_status
    if is_terminal:
        row.duration_seconds = int(duration) if duration else None
        row.completed_at = datetime.now(UTC)
    db.commit()

    if is_terminal and should_retry(our_status, row.attempt_number):
        retry_row = CallLog(
            customer_phone=row.customer_phone,
            ticket_id=row.ticket_id,
            parent_call_log_id=row.id,
            attempt_number=row.attempt_number + 1,
            status="queued",
        )
        db.add(retry_row)
        db.commit()
        logger.info(
            "status webhook: call_id=%s retry queued as call_id=%s (attempt_number=%d)",
            row.id, retry_row.id, retry_row.attempt_number,
        )
        place_outbound_call.delay(retry_row.id)

    return Response(status_code=204)
