"""Top-K retrieval from the pgvector store for an Arabic query.

Module: Conversation/RAG.
"""
from app.conversation.rag import embeddings, vectorstore


def retrieve(query_ar: str, top_k: int = 5) -> list[dict]:
    """Return the top-K matching chunks for an Arabic question, best first.

    Contract (consumed by answer.py in Sprint 3 — citations are a hard
    requirement, so source metadata must survive):

        {
            "text": str,              # the passage to cite
            "score": float,           # cosine similarity, higher = better
            "doc_id": int,
            "title": str,             # source document title
            "chunk_index": int,
            "source_uri": str | None, # original file/wiki location
        }
    """
    from app.data.db import SessionLocal

    vector = embeddings.embed_query(query_ar)
    with SessionLocal() as db:
        return vectorstore.query_chunks(db, vector, top_k)
