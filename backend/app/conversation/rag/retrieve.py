"""Hybrid top-K retrieval: pgvector similarity + BM25, merged by rank fusion.

Module: Conversation/RAG. Two arms score every query — dense cosine similarity
over pgvector (paraphrase-robust) and Okapi BM25 over normalized chunk text
(exact terms: ticket codes, product names, rare KB vocabulary) — and merge via
reciprocal-rank fusion, so a chunk both arms like beats one either arm alone
likes, without having to calibrate cosine scores against BM25 scores.
"""
from app.conversation.rag import embeddings, lexical, vectorstore

# RRF: score(chunk) = Σ over arms of 1 / (K + rank). 60 is the standard constant
# from the RRF paper. Each arm over-fetches CANDIDATE_FACTOR × top_k so fusion
# sees genuine overlap instead of two nearly disjoint short lists.
_RRF_K = 60
_CANDIDATE_FACTOR = 3


def retrieve(
    query_ar: str,
    top_k: int = 5,
    vector: list[float] | None = None,
    *,
    diagnostics: dict | None = None,
) -> list[dict]:
    """Return the top-K matching chunks for an Arabic question, best first.

    `vector` is an optional precomputed embedding of `query_ar` — answer.py
    embeds once and shares it between the semantic query cache and retrieval.

    `diagnostics`, when passed, is populated as a side effect (the returned list
    is unchanged) with `top_similarity`: the highest raw cosine similarity (0-1)
    from the dense arm, or None if nothing was retrieved. RRF fusion below flattens
    absolute relevance into rank positions, so this is captured beforehand — it is
    the honest "is anything actually on-topic?" signal the KB-gap log gates on.

    Contract (consumed by answer.py — citations are a hard requirement, so
    source metadata must survive):

        {
            "text": str,              # the passage to cite
            "score": float,           # fused RRF score, higher = better
            "doc_id": int,
            "title": str,             # source document title
            "chunk_index": int,
            "source_uri": str | None, # original file/wiki location
        }
    """
    from app.data.db import SessionLocal

    pool = top_k * _CANDIDATE_FACTOR
    if vector is None:
        vector = embeddings.embed_query(query_ar)
    with SessionLocal() as db:
        semantic = vectorstore.query_chunks(db, vector, pool)
        corpus = vectorstore.all_chunks(db)
    if diagnostics is not None:
        # query_chunks orders by cosine distance ascending, so semantic[0] is the
        # nearest chunk and its `score` (1 - distance) is the query's best cosine.
        diagnostics["top_similarity"] = semantic[0]["score"] if semantic else None
    lexical_hits = lexical.rank(query_ar, [row["text"] for row in corpus], pool)

    fused: dict[tuple[int, int], dict] = {}

    def accumulate(rank: int, row: dict) -> None:
        key = (row["doc_id"], row["chunk_index"])
        entry = fused.setdefault(key, {**row, "score": 0.0})
        entry["score"] += 1.0 / (_RRF_K + rank + 1)

    for rank, row in enumerate(semantic):
        accumulate(rank, row)
    for rank, (index, _bm25) in enumerate(lexical_hits):
        accumulate(rank, corpus[index])

    ranked = sorted(fused.values(), key=lambda row: -row["score"])
    return ranked[:top_k]
