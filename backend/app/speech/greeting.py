"""Dynamic Arabic greeting scripts for outbound follow-up calls.

Module: Speech Processing (Sprint 2). Builds the opening line the customer
hears when they answer, interpolating details carried over from the prior
inbound call (name, ticket ID, the procedure that was discussed), then renders
it through tts.synthesize.

The text is kept here — not in telephony — because it is the Speech module's
job to shape what the voice actually says; telephony just plays the bytes.
Digits (ticket IDs) are left as digits on purpose: ElevenLabs text
normalization voices them (requires ELEVENLABS_TEXT_NORMALIZATION=on — with
"auto" ElevenLabs tends to skip Arabic and reads digits wrong).
"""
from dataclasses import dataclass

from app.speech.tts import synthesize


@dataclass(frozen=True)
class GreetingContext:
    """What the prior inbound call left us to follow up on. All optional —
    the script degrades gracefully when a field is missing."""

    customer_name: str | None = None
    ticket_id: str | None = None
    procedure: str | None = None  # what the customer was asked to do / what was resolved


def follow_up_question(ctx: GreetingContext) -> str:
    """Compose the yes/no follow-up question for `ctx`."""
    if ctx.procedure:
        return f"هل تمكّنت من {ctx.procedure.strip()}؟"
    return "هل تم حل مشكلتك بنجاح؟"


def greeting_text(ctx: GreetingContext) -> str:
    """Compose the Arabic greeting + follow-up question for `ctx`.

    Shape: salutation (+ name) → who is calling and why (+ ticket) →
    the follow-up question (about the procedure, or a generic resolution check).
    """
    salutation = "مرحبًا"
    if ctx.customer_name:
        salutation += f" {ctx.customer_name.strip()}"

    intro = "معك المساعد الآلي من خدمة العملاء، ونتواصل معك للمتابعة"
    if ctx.ticket_id:
        intro += f" بخصوص طلبك رقم {ctx.ticket_id.strip()}"

    return f"{salutation}، {intro}. {follow_up_question(ctx)}"


def render_greeting(ctx: GreetingContext, voice: str | None = None) -> bytes:
    """Build the greeting for `ctx` and synthesize it to audio bytes."""
    return synthesize(greeting_text(ctx), voice=voice)
