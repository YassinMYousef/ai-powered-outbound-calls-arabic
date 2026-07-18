"""Arabic reply scripts for outbound follow-up calls.

Module: Speech Processing. Spoken wording belongs here so telephony only
orchestrates playback and call control.
"""
from app.speech.greeting import GreetingContext, follow_up_question

OFFER_HELP_AR = (
    "نأسف لأن المشكلة لم تُحل بعد. يسعدنا تقديم المزيد من المساعدة. "
    "هل تم حل مشكلتك الآن؟"
)
TRANSFER_AR = "يرجى الانتظار، جارٍ تحويل مكالمتك إلى أحد ممثلي خدمة العملاء."
TRANSFER_UNAVAILABLE_AR = (
    "نعتذر، لا يتوفر ممثل لخدمة العملاء الآن. سيتواصل معك أحد ممثلينا لاحقًا. "
    "شكرًا لك، ومع السلامة."
)
RESOLVED_GOODBYE_AR = "يسعدنا أن مشكلتك قد حُلّت. شكرًا لتواصلك معنا، ومع السلامة."


def repeat_question_text(ctx: GreetingContext) -> str:
    """Apologize for unclear speech and repeat the original follow-up question."""
    return f"عذرًا، لم أسمع إجابتك بوضوح. {follow_up_question(ctx)}"
