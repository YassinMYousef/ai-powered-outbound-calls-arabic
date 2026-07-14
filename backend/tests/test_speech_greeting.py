"""Speech greeting (Sprint 2) — dynamic Arabic script assembly."""
from app.speech import greeting
from app.speech.greeting import GreetingContext, greeting_text


def test_full_context_includes_all_details() -> None:
    text = greeting_text(GreetingContext(
        customer_name="أحمد",
        ticket_id="12345",
        procedure="تحديث بياناتك على النظام",
    ))
    assert "أحمد" in text
    assert "12345" in text            # digits left for TTS normalization to voice
    assert "تحديث بياناتك على النظام" in text
    assert text.startswith("مرحبًا")
    assert text.rstrip().endswith("؟")  # ends on the follow-up question


def test_missing_procedure_falls_back_to_generic_question() -> None:
    text = greeting_text(GreetingContext(customer_name="سارة", ticket_id="7"))
    assert "هل تم حل مشكلتك بنجاح؟" in text


def test_missing_name_and_ticket_still_valid() -> None:
    text = greeting_text(GreetingContext(procedure="إعادة ضبط الجهاز"))
    assert text.startswith("مرحبًا،")
    assert "إعادة ضبط الجهاز" in text
    assert "رقم" not in text  # no ticket phrase when ticket_id is absent


def test_render_greeting_synthesizes_the_built_text(monkeypatch) -> None:
    captured: dict = {}

    def fake_synthesize(text_ar, voice=None):
        captured["text"], captured["voice"] = text_ar, voice
        return b"AUDIO"

    monkeypatch.setattr(greeting, "synthesize", fake_synthesize)
    ctx = GreetingContext(customer_name="منى", ticket_id="99", procedure="الدفع")

    audio = greeting.render_greeting(ctx, voice="V1")

    assert audio == b"AUDIO"
    assert captured["text"] == greeting_text(ctx)
    assert captured["voice"] == "V1"
