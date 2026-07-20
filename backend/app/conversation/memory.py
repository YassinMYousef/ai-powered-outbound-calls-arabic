"""Chat-session memory: session lookup/creation and bounded history windows.

Module: Conversation. Every turn is persisted to app.data.models.{ChatSession,
ChatMessage}; only a bounded window is replayed to the model. Routes hand in
their request-scoped Session and own the transaction — create_session only
flushes, so a session row survives solely if its first turn commits.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import ChatMessage, ChatSession


def get_session(db: Session, session_id: int) -> ChatSession | None:
    """Return the session if it exists and has not ended, else None."""
    session = db.get(ChatSession, session_id)
    if session is None or session.ended_at is not None:
        return None
    return session


def create_session(db: Session) -> ChatSession:
    """Create an anonymous session (user_id stays NULL until OAuth2/RBAC lands).

    Flushes so the id is assigned, but does NOT commit — the caller commits
    after the first turn succeeds, so failed turns leave no empty sessions.
    """
    session = ChatSession()
    db.add(session)
    db.flush()
    return session


def load_history(db: Session, session_id: int, limit: int) -> list[dict]:
    """Last `limit` messages, oldest first, as {"role", "content"} dicts.

    Ordered by (created_at, id) descending then reversed — id breaks
    same-timestamp ties (SQLite in tests has second precision). Rides
    ix_chat_messages_session_created. The window is trimmed so it never
    starts with an assistant turn: the Messages API requires the first
    message of a conversation to be role "user".
    """
    rows = db.execute(
        select(ChatMessage.role, ChatMessage.content)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(limit)
    ).all()
    history = [{"role": role, "content": content} for role, content in reversed(rows)]
    while history and history[0]["role"] != "user":
        history.pop(0)
    return history


def append_turn(
    db: Session, session: ChatSession, query_ar: str, result: dict, latency_ms: int
) -> None:
    """Persist the user question + assistant answer atomically; touch updated_at.

    The user row stores the agent's original wording (not the retrieval
    rewrite) — history must read back exactly as the conversation happened.
    """
    db.add(ChatMessage(session_id=session.id, role="user", content=query_ar))
    db.add(
        ChatMessage(
            session_id=session.id,
            role="assistant",
            content=result["answer"],
            sources=result["sources"],
            latency_ms=latency_ms,
        )
    )
    # onupdate only fires when a mapped column changes; touch explicitly so a
    # session's updated_at always reflects its latest turn.
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
