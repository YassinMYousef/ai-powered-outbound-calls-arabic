"""Telephony provider webhook endpoints — the live half of the call loop.

Module: Telephony & Call Orchestration.
The provider POSTs here during a call; handlers must respond quickly (TwiML)
and be idempotent, because the provider retries on timeout.
"""
import logging

from fastapi import APIRouter, Request, Response
from twilio.twiml.voice_response import VoiceResponse

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
async def status(request: Request) -> Response:
    """Final call status (completed / no-answer / failed) → log outcome, maybe retry."""
    form = await request.form()
    logger.info(
        "call finished: sid=%s status=%s duration=%ss call_id=%s",
        form.get("CallSid"),
        form.get("CallStatus"),
        form.get("CallDuration"),
        request.query_params.get("call_id"),
    )
    # TODO: persist outcome to CallLog and hand to call_flow.should_retry.
    return Response(status_code=204)
