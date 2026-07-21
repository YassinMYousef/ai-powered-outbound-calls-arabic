"""Agent-facing RAG chatbot endpoint, consumed by the frontend ChatWidget.

Module: Conversation/NLU & RAG. Answers must be in Arabic and cite KB sources.
Conversations are stateful: each turn is persisted to chat_sessions /
chat_messages (conversation/memory.py), and a bounded history window is
replayed to the answer model so follow-up questions resolve.
"""
import logging
import time

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.conversation import memory
from app.conversation.rag import answer as answer_module
from app.data import audit, kb_gaps
from app.data.auth import require_role
from app.data.db import get_db
from app.data.models import User

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatQuery(BaseModel):
    query: str = Field(min_length=1)  # Arabic question from the agent
    top_k: int | None = Field(default=None, ge=1, le=20)  # passages to ground the answer in
    session_id: int | None = Field(default=None, ge=1)  # omit to start a new conversation


@router.post("/query")
def query(
    body: ChatQuery,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("agent")),
) -> dict:
    """Return {"session_id", "answer", "sources"} from the internal KB.

    Send the returned session_id with follow-up questions to continue the
    conversation; an unknown or ended session_id is a 404 (the client starts
    fresh). An empty "sources" list means the KB did not cover the question —
    the answer is a "not covered" notice, not a fact.

    Requires an authenticated agent (or higher); every query is audit-logged
    because it reads proprietary KB content.
    """
    if body.session_id is not None:
        session = memory.get_session(db, body.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="chat session not found")
        history = memory.load_history(db, session.id, settings.chat_history_max_messages)
    else:
        session = memory.create_session(db)  # flushed, only committed with a successful turn
        history = []
    session.user_id = user.id  # tie the conversation to the authenticated agent

    started = time.perf_counter()
    diagnostics: dict = {}
    try:
        result = answer_module.answer(
            body.query, body.top_k, history=history, diagnostics=diagnostics
        )
    except RuntimeError as exc:  # provider key missing, or the TEI embedder is down
        db.rollback()  # drop the uncommitted session row — no dangling unanswered turns
        logger.error("chat query unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Answer service is not configured") from exc
    except anthropic.APIError as exc:
        db.rollback()
        # Log the class, never the exception body — it can echo request content.
        logger.error("answer generation failed: %s", exc.__class__.__name__)
        raise HTTPException(status_code=502, detail="Answer generation failed") from exc

    latency_ms = int((time.perf_counter() - started) * 1000)
    # When the KB could not answer, log the question as a gap for admins to fill.
    # It joins this turn's transaction (append_turn commits both atomically); a
    # provider failure above already rolled the session back, so no gap leaks from
    # a turn the user never got. A query-cache hit sets no coverage → never a gap.
    coverage = diagnostics.get("coverage")
    if coverage in kb_gaps.GAP_REASONS:
        kb_gaps.record(
            db,
            query=body.query,
            reason=coverage,
            chunks_retrieved=diagnostics.get("chunks_retrieved"),
            top_similarity=diagnostics.get("top_similarity"),
            session_id=session.id,
        )
    memory.append_turn(db, session, body.query, result, latency_ms)
    audit.record(
        db,
        user_id=user.id,
        action="chat.query",
        resource_type="chat_session",
        resource_id=session.id,
        detail={"coverage": coverage, "sources": len(result.get("sources", []))},
    )
    return {"session_id": session.id, **result}
