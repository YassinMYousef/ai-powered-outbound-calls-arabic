"""Arabic dialog reply scripts owned by the speech module."""
from app.speech.greeting import GreetingContext
from app.speech.replies import (
    OFFER_HELP_AR,
    RESOLVED_GOODBYE_AR,
    TRANSFER_AR,
    TRANSFER_UNAVAILABLE_AR,
    repeat_question_text,
)


def test_reply_constants_are_non_empty_arabic() -> None:
    for phrase in (
        OFFER_HELP_AR,
        TRANSFER_AR,
        TRANSFER_UNAVAILABLE_AR,
        RESOLVED_GOODBYE_AR,
    ):
        assert phrase.strip()
        assert any("\u0600" <= char <= "\u06ff" for char in phrase)


def test_repeat_question_uses_procedure_question() -> None:
    text = repeat_question_text(GreetingContext(procedure="إعادة تشغيل الجهاز"))

    assert "هل تمكّنت من إعادة تشغيل الجهاز؟" in text


def test_repeat_question_uses_generic_resolution_question() -> None:
    text = repeat_question_text(GreetingContext())

    assert "هل تم حل مشكلتك بنجاح؟" in text
