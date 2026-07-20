"""Standalone-question rewrite for conversational follow-ups.

Module: Conversation/RAG. A follow-up like «وبعد كده أعمل إيه؟» retrieves
nothing on its own — neither arm of hybrid retrieval can see what «كده» refers
to. A cheap Haiku call condenses recent history + the follow-up into one
self-contained Arabic query, run BEFORE retrieval. The first turn of a session
has no history and skips the call entirely. Failure never blocks the turn: on
APIError the raw query is used (retrieval degrades; the request succeeds).
"""
import logging
from functools import lru_cache

import anthropic
from anthropic import Anthropic

from app.config import settings

logger = logging.getLogger(__name__)

REWRITE_SYSTEM = """The conversation is between a call-center agent and a \
knowledge-base assistant. Rewrite the agent's LAST question as ONE standalone \
Arabic question that can be understood without the conversation, resolving \
pronouns and references from earlier turns.

Rules:
- Output ONLY the rewritten question, in Arabic. No preamble, no quotes, no answer.
- Preserve the agent's intent exactly; never answer the question.
- If the question is already self-contained, return it unchanged."""


@lru_cache(maxsize=1)
def _client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY must be set for query rewriting")
    return Anthropic(api_key=settings.anthropic_api_key)


def rewrite_query(query_ar: str, history: list[dict]) -> str:
    """Return a standalone Arabic query for retrieval. No history -> no call."""
    if not history:
        return query_ar
    window = history[-settings.rewrite_history_max_messages :]
    try:
        # Haiku: no thinking/effort params, and the prompt sits far below the
        # minimum cacheable prefix, so no cache_control either.
        response = _client().messages.create(
            model=settings.rewrite_model,
            max_tokens=settings.rewrite_max_tokens,
            system=REWRITE_SYSTEM,
            messages=[*window, {"role": "user", "content": query_ar}],
        )
    except anthropic.APIError as exc:
        # Class only — the exception body can echo request content.
        logger.warning("query rewrite failed (%s); using raw query", exc.__class__.__name__)
        return query_ar
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        return query_ar
    logger.info(
        "query rewrite: history=%d chars_in=%d chars_out=%d", len(window), len(query_ar), len(text)
    )
    return text
