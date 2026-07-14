"""Outbound dialing via the telephony provider (Twilio; Vonage was the alternative).

Module: Telephony & Call Orchestration. Keep provider SDK calls behind this
wrapper so the provider stays swappable. Credentials come from app.config.settings.
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
    """Start an outbound call; the provider's webhooks point back at /telephony/*.

    Returns the provider call SID, which is stored on the CallLog row so
    webhook events can be correlated.
    """
    if not settings.twilio_from_number:
        raise RuntimeError("TWILIO_FROM_NUMBER must be set")

    # call_id rides on the webhook URLs so handlers can correlate without a SID lookup.
    query = urlencode({"call_id": call_id})
    call = _client().calls.create(
        to=to_number,
        from_=settings.twilio_from_number,
        url=f"{settings.public_base_url}/telephony/voice?{query}",
        status_callback=f"{settings.public_base_url}/telephony/status?{query}",
        status_callback_event=["completed"],
        status_callback_method="POST",
    )
    return call.sid
