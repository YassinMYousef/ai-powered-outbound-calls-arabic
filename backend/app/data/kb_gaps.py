"""The unanswered-question (KB gap) log: record gaps, and read/resolve them.

Module: Backend/Data. A "gap" is a chat turn the KB could not answer — the
verdict comes from conversation/rag/answer.py (see `_coverage`). `record` runs
inside the chat turn's transaction (it only adds, never commits) so a failed
turn leaves no dangling gap; the admin-review side (`list_gaps`, `resolve`) owns
its own transaction.

Repeats are grouped by `normalized_query` — the same Arabic normalization the
lexical retrieval arm uses (conversation/rag/lexical.tokenize) — so "كيف أفعّل
الشريحة؟" and "كيف افعل الشريحه" collapse into one gap the review UI can rank by
how often agents hit it.
"""
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.conversation.rag import lexical
from app.data.models import UnansweredQuestion

# The coverage verdicts that count as a gap (mirrors the CHECK constraint on the
# model). answer.py's other verdicts — "covered", "refused" — are never logged.
GAP_REASONS = frozenset({"no_match", "no_citation", "low_confidence"})
# The states an open gap can be moved to from the review UI.
RESOLVABLE_STATUSES = frozenset({"resolved", "dismissed"})


def _normalize(query: str) -> str:
    """The grouping key: Arabic-normalized tokens joined back into a string."""
    return " ".join(lexical.tokenize(query))


def record(
    db: Session,
    *,
    query: str,
    reason: str,
    chunks_retrieved: int | None = None,
    top_similarity: float | None = None,
    session_id: int | None = None,
) -> UnansweredQuestion | None:
    """Add one gap row to the caller's transaction (no commit). Returns None — and
    adds nothing — when logging is disabled or `reason` is not a gap verdict."""
    if not settings.kb_gap_logging_enabled or reason not in GAP_REASONS:
        return None
    row = UnansweredQuestion(
        query=query,
        normalized_query=_normalize(query),
        reason=reason,
        chunks_retrieved=chunks_retrieved,
        top_similarity=top_similarity,
        session_id=session_id,
    )
    db.add(row)
    return row


def list_gaps(db: Session, status: str = "open", limit: int = 50) -> list[dict]:
    """Gaps in `status`, grouped by normalized_query, most-hit first.

    Grouping is done in Python (the log is a low-volume ops table) so the query
    stays portable across Postgres and SQLite. Each group is API-ready:

        {
            "normalized_query": str,
            "sample_query": str,          # the most recent original wording
            "count": int,                 # occurrences in this status
            "reason": str,                # the group's most common gap verdict
            "reasons": {reason: count},   # full breakdown
            "top_similarity": float | None,  # from the most recent occurrence
            "first_seen": str | None,     # ISO 8601
            "last_seen": str | None,      # ISO 8601
        }
    """
    rows = db.execute(
        select(UnansweredQuestion)
        .where(UnansweredQuestion.status == status)
        .order_by(UnansweredQuestion.created_at.desc(), UnansweredQuestion.id.desc())
    ).scalars().all()

    groups: dict[str, dict] = {}
    for row in rows:
        group = groups.get(row.normalized_query)
        if group is None:
            # Rows arrive newest-first, so the first one seen carries the latest
            # wording, similarity, and last_seen for the group.
            group = {
                "normalized_query": row.normalized_query,
                "sample_query": row.query,
                "count": 0,
                "reasons": Counter(),
                "top_similarity": row.top_similarity,
                "first_seen": row.created_at,
                "last_seen": row.created_at,
            }
            groups[row.normalized_query] = group
        group["count"] += 1
        group["reasons"][row.reason] += 1
        if row.created_at is not None and (
            group["first_seen"] is None or row.created_at < group["first_seen"]
        ):
            group["first_seen"] = row.created_at

    # groups.values() is already newest-first (dicts keep insertion order, and rows
    # were fetched newest-first). A stable sort by count keeps that recency order as
    # the tiebreak — no datetime comparison, so naive/aware mixing can't bite.
    ordered = sorted(groups.values(), key=lambda g: g["count"], reverse=True)
    return [_serialize(group) for group in ordered[:limit]]


def _serialize(group: dict) -> dict:
    reasons = group["reasons"]
    return {
        "normalized_query": group["normalized_query"],
        "sample_query": group["sample_query"],
        "count": group["count"],
        "reason": reasons.most_common(1)[0][0],
        "reasons": dict(reasons),
        "top_similarity": group["top_similarity"],
        "first_seen": group["first_seen"].isoformat() if group["first_seen"] else None,
        "last_seen": group["last_seen"].isoformat() if group["last_seen"] else None,
    }


def resolve(
    db: Session,
    *,
    normalized_query: str,
    status: str,
    note: str | None = None,
    user_id: int | None = None,
) -> int:
    """Flip every OPEN row sharing `normalized_query` to `status`; commit; return
    how many rows changed. A later occurrence opens a fresh row, so a recurring
    gap resurfaces on its own rather than staying silently resolved."""
    if status not in RESOLVABLE_STATUSES:
        raise ValueError(f"status must be one of {sorted(RESOLVABLE_STATUSES)}")
    result = db.execute(
        update(UnansweredQuestion)
        .where(
            UnansweredQuestion.normalized_query == normalized_query,
            UnansweredQuestion.status == "open",
        )
        .values(
            status=status,
            resolution_note=note,
            resolved_by_user_id=user_id,
            resolved_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return result.rowcount
