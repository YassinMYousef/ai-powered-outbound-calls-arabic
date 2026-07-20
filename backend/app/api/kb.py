"""Knowledge-base document management — upload docs and trigger (re-)ingestion.

Module: Backend/Data (storage) + Conversation/RAG (embedding pipeline).
Access is role-restricted once app/data/auth.py lands.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conversation.rag.extract import extract_text
from app.data import kb_gaps
from app.data.db import get_db
from app.data.models import KBDocument

logger = logging.getLogger(__name__)
router = APIRouter()


def _enqueue_ingest(doc_id: int) -> None:
    """Best-effort immediate embed; the nightly batch is the guaranteed path.

    retry=False so a dead broker fails fast instead of blocking the request.
    """
    from app.workers.tasks import ingest_kb_document

    try:
        ingest_kb_document.apply_async(args=[doc_id], retry=False)
    except Exception:
        logger.warning("could not enqueue ingest for KB doc %s (is Redis up?)", doc_id)


@router.post("/documents", status_code=202)
def upload_document(file: UploadFile, db: Session = Depends(get_db)) -> dict:
    """Store a KB document (txt/md/pdf/docx) and enqueue embedding."""
    filename = file.filename or ""
    try:
        text = extract_text(file.file.read(), filename)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    if not text.strip():
        raise HTTPException(status_code=400, detail="document contains no extractable text")

    doc = KBDocument(title=Path(filename).stem or filename, source_uri=filename, content=text)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    _enqueue_ingest(doc.id)
    return {"id": doc.id, "title": doc.title, "status": "pending_embedding"}


@router.get("/documents")
def list_documents(db: Session = Depends(get_db)) -> list[dict]:
    """List KB documents with their last-embedded timestamps (knowledge coverage KPI)."""
    docs = (
        db.execute(select(KBDocument).order_by(KBDocument.created_at.desc(), KBDocument.id.desc()))
        .scalars()
        .all()
    )
    return [
        {
            "id": doc.id,
            "title": doc.title,
            "source_uri": doc.source_uri,
            "embedded_at": doc.embedded_at.isoformat() if doc.embedded_at else None,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
        for doc in docs
    ]


# --- Unanswered questions (KB gaps) ---------------------------------------
# Questions the RAG chatbot could not answer, recorded per chat turn by
# app.api.chat and grouped for review here. Admins act on these by uploading the
# missing KB documents above, which closes the gap on the next ingest.


class GapResolution(BaseModel):
    normalized_query: str = Field(min_length=1)  # the group key from GET /gaps
    status: str = Field(pattern="^(resolved|dismissed)$")
    note: str | None = Field(default=None, max_length=2000)  # e.g. which doc was added


@router.get("/gaps")
def list_gaps(
    status: str = Query(default="open", pattern="^(open|resolved|dismissed)$"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Unanswered questions grouped by normalized text, most-hit first.

    Each group carries a `count` (how often it was asked), the latest wording, the
    gap `reason`, and last-seen — so admins fill the highest-impact gaps first.

    TODO(auth): guard with data/auth.require_role("admin") once OAuth2/RBAC lands.
    """
    return kb_gaps.list_gaps(db, status=status, limit=limit)


@router.post("/gaps/resolve")
def resolve_gap(body: GapResolution, db: Session = Depends(get_db)) -> dict:
    """Mark every open gap sharing this normalized_query resolved or dismissed.

    Returns {"updated": n}. If the gap recurs later it opens a fresh row, so a
    resolved-but-still-missing topic resurfaces on its own.

    TODO(auth): guard with data/auth.require_role("admin") once OAuth2/RBAC lands.
    """
    updated = kb_gaps.resolve(
        db, normalized_query=body.normalized_query, status=body.status, note=body.note
    )
    return {"updated": updated}
