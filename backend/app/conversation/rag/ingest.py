"""KB ingestion pipeline: chunk → embed → store in pgvector.

Module: Conversation/RAG. Runs nightly via workers/tasks.py::ingest_kb_documents
and on demand when a document is uploaded through /api/kb/documents (text
extraction happens at upload time — KBDocument.content is already plain text).

Collaborators are called as module attributes (embeddings.embed_passages, …)
so tests can monkeypatch them in one place.
"""
import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.conversation.rag import chunking, embeddings, query_cache, vectorstore
from app.data.models import KBDocument


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def docs_needing_embedding(db: Session) -> list[int]:
    """Ids of documents never embedded, or whose content changed since the last embed."""
    docs = db.execute(select(KBDocument)).scalars().all()
    return [
        doc.id
        for doc in docs
        if doc.embedded_at is None or doc.content_hash != content_sha256(doc.content or "")
    ]


def ingest_document(doc_id: int, db: Session | None = None) -> int:
    """Chunk, embed, and store one document. Returns the number of chunks embedded.

    Stamps embedded_at + content_hash in the same transaction as the chunk
    swap — even for zero chunks, so the nightly job stops re-picking empty docs.
    """
    if db is None:
        from app.data.db import SessionLocal

        with SessionLocal() as owned:
            return ingest_document(doc_id, db=owned)

    doc = db.get(KBDocument, doc_id)
    if doc is None:
        raise ValueError(f"KBDocument {doc_id} not found")

    chunks = chunking.chunk_text(
        doc.content or "", settings.rag_chunk_size, settings.rag_chunk_overlap
    )
    vectors = embeddings.embed_passages(chunks) if chunks else []
    vectorstore.replace_doc_chunks(
        db, doc_id, [(i, text, vec) for i, (text, vec) in enumerate(zip(chunks, vectors))]
    )
    doc.embedded_at = datetime.now(timezone.utc)
    doc.content_hash = content_sha256(doc.content or "")
    db.commit()
    # After commit (a failed ingest must not flush a still-valid cache): cached
    # answers may cite the pre-change KB, so both query-cache levels are dropped.
    query_cache.invalidate_all()
    return len(chunks)
