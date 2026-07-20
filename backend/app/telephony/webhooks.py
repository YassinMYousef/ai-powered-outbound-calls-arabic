"""Telephony provider webhook endpoints — the live half of the call loop.

Module: Telephony & Call Orchestration.
The provider POSTs here during a call; handlers must respond quickly (TwiML)
and be idempotent, because the provider retries on timeout.
"""
import logging
from collections.abc import Iterator
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse

from app.config import settings
from app.conversation.dialog import Action, DialogState, classify_intent, next_action
from app.data.db import get_db
from app.data.models import CallLog
from app.speech import audio, stt, tts
from app.speech.greeting import GreetingContext, greeting_text
from app.speech.replies import (
    OFFER_HELP_AR,
    RESOLVED_GOODBYE_AR,
    TRANSFER_AR,
    TRANSFER_UNAVAILABLE_AR,
    repeat_question_text,
)
from app.telephony import audio_store, client

router = APIRouter()
logger = logging.getLogger(__name__)

GREETING_AR = "مرحبًا بك. هذه مكالمة متابعة للتأكد من أن مشكلتك قد تم حلها."

# Polly.Zeina is Modern Standard Arabic (language code "arb"); Twilio has no
# Egyptian-dialect voice.
_AR_VOICE = "Polly.Zeina"
_AR_LANG = "arb"
DIAL_TIMEOUT = 20


def _twiml(response: VoiceResponse) -> Response:
    return Response(content=str(response), media_type="application/xml")


def _load_call(db: Session, call_id: int | None) -> CallLog | None:
    if call_id is None:
        return None
    call = db.get(CallLog, call_id)
    if call is None:
        logger.warning("call log %s was not found", call_id)
    return call


def _greeting_ctx(call: CallLog | None) -> GreetingContext:
    return GreetingContext(ticket_id=call.ticket_id if call else None)


def _say_or_play(response: VoiceResponse, text_ar: str) -> None:
    try:
        token = audio_store.store_text(text_ar)
        response.play(audio_store.play_url(token))
    except Exception:
        logger.exception("could not store telephony speech; falling back to Twilio Say")
        response.say(text_ar, voice=_AR_VOICE, language=_AR_LANG)


def _record_turn(response: VoiceResponse, call_id: int | None, turn: int) -> None:
    query = [("turn", turn)]
    if call_id is not None:
        query.insert(0, ("call_id", call_id))
    action = f"/telephony/gather?{urlencode(query)}"
    # timeout is the endpoint: Twilio keeps recording while the caller speaks
    # and stops after that many seconds of silence; max_length is only a cap.
    response.record(
        action=action,
        method="POST",
        max_length=settings.record_max_length_seconds,
        timeout=settings.record_silence_timeout_seconds,
        play_beep=False,
        trim="trim-silence",
    )
    response.redirect(action, method="POST")


def _append_transcript(
    db: Session,
    call: CallLog,
    turn: int,
    transcript: str,
    action: Action,
) -> None:
    marker = f"[turn {turn}]"
    if marker in (call.transcript or ""):
        return
    line = f"{marker} customer: {transcript or '<no speech>'} -> {action.value}"
    call.transcript = f"{call.transcript}\n{line}" if call.transcript else line
    db.commit()


@router.post("/voice")
def voice(call_id: int | None = None, db: Session = Depends(get_db)) -> Response:
    """Play a dynamic Arabic greeting, then record the customer's first turn."""
    call = _load_call(db, call_id)
    response = VoiceResponse()
    _say_or_play(response, greeting_text(_greeting_ctx(call)))
    _record_turn(response, call_id, 0)
    return _twiml(response)


@router.post("/gather")
def gather(
    call_id: int | None = None,
    turn: int = 0,
    RecordingUrl: str | None = Form(None),
    SpeechResult: str | None = Form(None),
    CallSid: str | None = Form(None),
    db: Session = Depends(get_db),
) -> Response:
    """Transcribe one customer turn and return the dialog's next TwiML action."""
    transcript = ""
    if RecordingUrl:
        try:
            recording = client.fetch_recording_wav(RecordingUrl)
            transcript = stt.transcribe(audio.wav_to_stt_wav(recording))
        except Exception:
            logger.exception("could not transcribe Twilio recording for call %s", CallSid)
    elif SpeechResult:
        transcript = SpeechResult

    intent = classify_intent(transcript)
    call = _load_call(db, call_id)
    state = DialogState(
        call_id=call_id or 0,
        ticket_id=call.ticket_id if call else None,
        turn=turn,
    )
    action = next_action(state, intent)
    if call:
        _append_transcript(db, call, turn, transcript, action)

    response = VoiceResponse()
    if action is Action.MARK_RESOLVED:
        if call:
            call.outcome = "resolved"
            db.commit()
        _say_or_play(response, RESOLVED_GOODBYE_AR)
        response.hangup()
    elif action is Action.OFFER_HELP:
        _say_or_play(response, OFFER_HELP_AR)
        _record_turn(response, call_id, turn + 1)
    elif action is Action.REPEAT_QUESTION:
        _say_or_play(response, repeat_question_text(_greeting_ctx(call)))
        _record_turn(response, call_id, turn + 1)
    elif action is Action.TRANSFER_TO_AGENT:
        if settings.human_agent_number:
            if call:
                call.outcome = "transferred"
                db.commit()
            _say_or_play(response, TRANSFER_AR)
            response.dial(
                settings.human_agent_number,
                timeout=DIAL_TIMEOUT,
                caller_id=settings.twilio_from_number,
            )
            response.say(TRANSFER_UNAVAILABLE_AR, voice=_AR_VOICE, language=_AR_LANG)
            response.hangup()
        else:
            if call:
                call.outcome = "unresolved"
                db.commit()
            _say_or_play(response, TRANSFER_UNAVAILABLE_AR)
            response.hangup()
    return _twiml(response)


@router.get("/audio/{token}")
def streamed_audio(token: str) -> Response:
    """Resolve a text token and stream or return cached ElevenLabs audio."""
    try:
        text_ar = audio_store.fetch_text(token)
    except RedisError as exc:
        logger.warning("could not resolve telephony audio token", exc_info=True)
        raise HTTPException(status_code=503, detail="audio store unavailable") from exc
    if text_ar is None:
        raise HTTPException(status_code=404, detail="audio token not found")

    media_type = audio_store.audio_content_type()
    cached = audio_store.get_cached_audio(text_ar)
    if cached is not None:
        return Response(content=cached, media_type=media_type)

    try:
        stream = iter(tts.synthesize_stream(text_ar))
        first_chunk = next(stream)
    except Exception as exc:
        logger.exception("could not start telephony TTS stream")
        raise HTTPException(status_code=404, detail="audio unavailable") from exc

    def generate() -> Iterator[bytes]:
        chunks = [first_chunk]
        yield first_chunk
        for chunk in stream:
            chunks.append(chunk)
            yield chunk
        audio_store.cache_audio(text_ar, b"".join(chunks))

    return StreamingResponse(generate(), media_type=media_type)


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
            customer_id=row.customer_id,
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
        # Best-effort, same pattern as api/calls.py's _enqueue_dial: a dead
        # broker must not turn a webhook response into a 500 for Twilio. The
        # row stays "queued" either way — schedule_follow_up_batch will pick
        # it up on the next run if this enqueue is lost.
        try:
            place_outbound_call.apply_async(args=[retry_row.id], retry=False)
        except Exception:
            logger.warning("could not enqueue retry dial for call %s (is Redis/the worker up?)", retry_row.id)

    return Response(status_code=204)
