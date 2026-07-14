"""Agent-facing RAG chatbot endpoint, consumed by the frontend ChatWidget.

Module: Conversation/NLU & RAG. Answers must be in Arabic and cite KB sources.
"""
import logging

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.conversation.rag import answer as answer_module

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatQuery(BaseModel):
    query: str = Field(min_length=1)  # Arabic question from the agent
    top_k: int | None = Field(default=None, ge=1, le=20)  # passages to ground the answer in


@router.post("/query")
def query(body: ChatQuery) -> dict:
    """Return {"answer": <Arabic answer>, "sources": [...]} from the internal KB.

    Delegates to app/conversation/rag/answer.py. An empty "sources" list means the
    KB did not cover the question — the answer is a "not covered" notice, not a fact.

    TODO(auth): guard with data/auth.require_role once OAuth2/RBAC lands (Person D,
    Sprint 3) — KB content is proprietary and this route exposes it unauthenticated.
    """
    try:
        return answer_module.answer(body.query, body.top_k)
    except RuntimeError as exc:  # provider key missing, or the TEI embedder is down
        logger.error("chat query unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Answer service is not configured") from exc
    except anthropic.APIError as exc:
        # Log the class, never the exception body — it can echo request content.
        logger.error("answer generation failed: %s", exc.__class__.__name__)
        raise HTTPException(status_code=502, detail="Answer generation failed") from exc
