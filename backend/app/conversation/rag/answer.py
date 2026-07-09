"""Cited answer generation over retrieved KB passages.

Module: Conversation/RAG. The planning docs name GPT-4 Turbo; keep the LLM
call isolated here so the model/provider can be swapped without touching the
retrieval pipeline or the API layer.
"""


def answer(query_ar: str) -> dict:
    """Return {"answer": <concise Arabic answer>, "sources": [<snippet + origin>, ...]}.

    Example target output (requirements doc §4):
    "يمكنك تحديث بيانات العميل عبر الدخول إلى… (المصدر: قسم العمليات، صفحة 12)"
    """
    raise NotImplementedError
