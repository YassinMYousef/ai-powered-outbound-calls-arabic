"""Outbound dialing via Twilio.
Module: Telephony & Call Orchestration. Credentials come from app.config.settings.
"""
from functools import lru_cache
from urllib.parse import urlencode

from twilio.rest import Client

from app.config import settings


@lru_cache(maxsize=1)
def _client() -> Client:
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        raise RuntimeError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set")
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def place_call(to_number: str, call_id: int) -> str:
    """Start an outbound call. Twilio will hit our webhooks at /telephony/voice
    and /telephony/status once the call connects / ends.
    Returns the Twilio call SID.
    """
    if not settings.twilio_from_number:
        raise RuntimeError("TWILIO_FROM_NUMBER must be set")
    if not settings.public_base_url:
        raise RuntimeError("PUBLIC_BASE_URL must be set (ngrok URL for local testing)")

    query = urlencode({"call_id": call_id})
    call = _client().calls.create(
        to=to_number,
        from_=settings.twilio_from_number,
        url=f"{settings.public_base_url}/telephony/voice?{query}",
        status_callback=f"{settings.public_base_url}/telephony/status?{query}",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST",
    )
    return call.sid


def transfer_to_agent(provider_call_sid: str, to_number: str) -> None:
    """Redirect a live call to a human agent via <Dial>, replacing its TwiML."""
    from twilio.twiml.voice_response import VoiceResponse

    twiml = VoiceResponse()
    twiml.dial(to_number)
    _client().calls(provider_call_sid).update(twiml=str(twiml))