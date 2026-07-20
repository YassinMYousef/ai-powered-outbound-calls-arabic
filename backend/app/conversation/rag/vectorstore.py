"""Vector storage and similarity search over Postgres/pgvector (kb_chunks).

Module: Conversation/RAG. Sessions are passed in — chunk writes join the
caller's transaction (ingest stamps embedded_at atomically with its chunks).
Similarity queries need pgvector, so query_chunks is Postgres-only at runtime;
tests fake this module.
"""
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.data.models import KBChunk, KBDocument


def replace_doc_chunks(
    db: Session, doc_id: int, chunks: list[tuple[int, str, list[float]]]
) -> None:
    """Swap a document's chunks wholesale — (chunk_index, text, embedding) triples.

    Does not commit; the caller owns the transaction.
    """
    db.execute(delete(KBChunk).where(KBChunk.document_id == doc_id))
    db.add_all(
        KBChunk(document_id=doc_id, chunk_index=index, text=text, embedding=vector)
        for index, text, vector in chunks
    )


def all_chunks(db: Session) -> list[dict]:
    """Every chunk with its source-document metadata, for in-process BM25 scoring.

    The KB is an internal ops corpus (hundreds of chunks, not millions), so the
    lexical arm re-reads it per query; revisit with a cached index or a Postgres
    BM25 extension if it outgrows that.
    """
    rows = db.execute(
        select(KBChunk, KBDocument).join(KBDocument, KBChunk.document_id == KBDocument.id)
    ).all()
    return [
        {
            "text": chunk.text,
            "doc_id": doc.id,
            "title": doc.title,
            "chunk_index": chunk.chunk_index,
            "source_uri": doc.source_uri,
        }
        for chunk, doc in rows
    ]


def query_chunks(db: Session, embedding: list[float], top_k: int) -> list[dict]:
    """Top-K nearest chunks by cosine distance, joined with their source document."""
    distance = KBChunk.embedding.cosine_distance(embedding)
    rows = db.execute(
        select(KBChunk, KBDocument, distance.label("distance"))
        .join(KBDocument, KBChunk.document_id == KBDocument.id)
        .order_by(distance)
        .limit(top_k)
    ).all()
    return [
        {
            "text": chunk.text,
            "score": 1.0 - dist,  # cosine similarity — higher is better
            "doc_id": doc.id,
            "title": doc.title,
            "chunk_index": chunk.chunk_index,
            "source_uri": doc.source_uri,
        }
        for chunk, doc, dist in rows
    ]
