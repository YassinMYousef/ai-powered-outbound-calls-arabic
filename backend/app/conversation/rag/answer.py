"""Cited answer generation over retrieved KB passages.

Module: Conversation/RAG. Keep the LLM call isolated here so the model/provider
can be swapped without touching retrieval or the API layer.

Citations are a hard product requirement, so they are NOT prompted for — asking
the model to write "(المصدر: ...)" inline lets it invent a source. Instead each
retrieved chunk is sent as its own plain-text `document` block with citations
enabled, and the model returns citation objects bound to exact character spans
of the passages we supplied. A citation therefore cannot reference a document
that was never retrieved; resolving it back to a KBDocument happens in code below.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from anthropic import Anthropic

from app.config import settings
from app.conversation.rag import embeddings, query_cache, retrieve, rewrite

logger = logging.getLogger(__name__)

# Agent-facing copy is Arabic (MSA); the instructions to the model are English.
NO_MATCH_AR = "لا توجد معلومات عن هذا الموضوع في قاعدة المعرفة الداخلية."
REFUSED_AR = "تعذر إنشاء إجابة لهذا السؤال. يرجى إعادة صياغته أو الرجوع إلى المشرف."

SYSTEM_PROMPT = """You answer questions from call-center agents using ONLY the \
knowledge-base documents supplied with each question.

Rules:
- Answer in Modern Standard Arabic. Be concise: 2-4 sentences.
- Use only the supplied documents. Never rely on outside knowledge, and never guess.
- If the documents do not contain the answer, say so plainly in Arabic instead of \
speculating — a wrong answer to an agent on a live call is worse than no answer.
- Your reader is a call-center employee handling a customer, not the customer \
themselves. Give them the procedure, not customer-facing pleasantries.
- State each fact exactly once. Do not restate or paraphrase a step you have already \
written — write the sentence once, drawing it from the document.
- Ground every sentence in the supplied documents so the citation system can \
attach the exact passages you relied on. Never write textual source references \
like "(المصدر: ...)" yourself — only the attached citations name sources.
- The conversation may span several turns. Earlier turns are context for \
understanding the latest question only — ground every fact in the documents \
supplied with the latest question, never in your own earlier answers."""


@lru_cache(maxsize=1)
def _executor() -> ThreadPoolExecutor:
    # Runs retrieval concurrently with the L1 semantic-cache lookup. Module-level
    # on purpose: an L1 hit ABANDONS its retrieval future, and a per-request
    # `with ThreadPoolExecutor(...)` would block the hit's return on shutdown(wait=True).
    return ThreadPoolExecutor(max_workers=4, thread_name_prefix="rag-retrieve")


@lru_cache(maxsize=1)
def _client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY must be set for RAG answer generation")
    return Anthropic(api_key=settings.anthropic_api_key)


def _documents(chunks: list[dict]) -> list[dict]:
    """One plain-text document block per retrieved chunk.

    Per-chunk documents (rather than one concatenated blob) are what let the model
    cite a specific sentence and let us resolve `document_index` back to a KBDocument.
    `context` rides along as metadata the model can read but can never cite from.
    """
    return [
        {
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": chunk["text"]},
            "title": chunk["title"],
            "context": f"doc_id={chunk['doc_id']} chunk={chunk['chunk_index']} "
            f"source={chunk['source_uri'] or 'unknown'}",
            "citations": {"enabled": True},
        }
        for chunk in chunks
    ]


def _sources(content: list, chunks: list[dict]) -> list[dict]:
    """Resolve the response's citations back to the chunks they cite.

    Only cited chunks appear, ordered by first citation and deduplicated, so the
    widget shows what actually backs the answer rather than everything retrieved.
    """
    sources: dict[int, dict] = {}
    for block in content:
        for citation in getattr(block, "citations", None) or []:
            index = getattr(citation, "document_index", None)
            if index is None or not 0 <= index < len(chunks):
                # A citation can only point at a document we sent, but a bad index
                # must not take down the agent's chat widget.
                logger.warning("citation with out-of-range document_index %r", index)
                continue
            chunk = chunks[index]
            source = sources.setdefault(
                index,
                {
                    "doc_id": chunk["doc_id"],
                    "title": chunk["title"],
                    "source_uri": chunk["source_uri"],
                    "chunk_index": chunk["chunk_index"],
                    "score": chunk["score"],
                    "quotes": [],
                },
            )
            quote = getattr(citation, "cited_text", "")
            if quote and quote not in source["quotes"]:
                source["quotes"].append(quote)
    return list(sources.values())


def _history_messages(history: list[dict]) -> list[dict]:
    """Prior turns as plain-text messages, oldest first.

    The LAST one carries a cache breakpoint: system + history is a stable
    prefix that only grows at its tail, while the per-question document blocks
    sit after it — so each turn reuses the previous turn's cache. (A no-op
    below the model's minimum cacheable prefix, same as the system breakpoint.)
    """
    messages = [{"role": turn["role"], "content": turn["content"]} for turn in history]
    messages[-1] = {
        "role": messages[-1]["role"],
        "content": [
            {
                "type": "text",
                "text": history[-1]["content"],
                "cache_control": {"type": "ephemeral"},
            }
        ],
    }
    return messages


def _coverage(chunks: list, sources: list, top_similarity: float | None) -> str:
    """Classify how well the KB backed this answer, for the gap log.

    'no_match' nothing retrieved · 'no_citation' passages retrieved but the
    grounded model cited none · 'low_confidence' cited, but the best passage's
    raw cosine is below the floor · 'covered' otherwise. ('refused' is set by
    the caller — a safety refusal is not a KB gap.)
    """
    if not chunks:
        return "no_match"
    if not sources:
        return "no_citation"
    if top_similarity is not None and top_similarity < settings.rag_gap_min_similarity:
        return "low_confidence"
    return "covered"


def answer(
    query_ar: str,
    top_k: int | None = None,
    history: list[dict] | None = None,
    *,
    diagnostics: dict | None = None,
) -> dict:
    """Answer an Arabic question from the KB, with the sources that back it.

    `history` is the prior conversation as {"role": "user"|"assistant",
    "content": str} dicts, oldest first (see conversation/memory.py). Prior
    turns are replayed as plain text — their document blocks are NOT resent,
    so `_sources` resolution stays scoped to the current turn's chunks. On
    follow-ups, retrieval runs on a standalone rewrite of the question while
    the prompt keeps the agent's original wording (history disambiguates it).

    `diagnostics`, when passed, is populated as a side effect (the returned dict
    is unchanged, so callers and the query cache see only {"answer", "sources"})
    with the retrieval verdict the KB-gap log reads: `coverage` (see _coverage),
    `chunks_retrieved`, and `top_similarity`. It stays untouched on a query-cache
    hit — a cached answer was cited when first generated, never a gap.

    Returns:
        {
            "answer": str,        # Arabic (MSA)
            "sources": [          # only the passages actually cited, best first
                {
                    "doc_id": int,
                    "title": str,
                    "source_uri": str | None,
                    "chunk_index": int,
                    "score": float,        # hybrid retrieval score (RRF-fused)
                    "quotes": [str, ...],  # exact spans the answer rests on
                },
                ...
            ],
        }

    An empty `sources` list means the KB did not support an answer — the caller
    must treat the reply as "not covered", never as an uncited fact.
    """
    retrieval_query = rewrite.rewrite_query(query_ar, history) if history else query_ar
    k = top_k or settings.rag_top_k

    # Two-level query cache, keyed on the standalone retrieval query. L0 (exact,
    # Redis) is a ~1ms GET, so it runs serially before anything else. On an L0
    # miss the query is embedded ONCE and the vector shared three ways: retrieval
    # (submitted to a thread) and the L1 semantic lookup (this thread) race in
    # parallel; a hit abandons the retrieval future — the started thread finishes
    # its DB work in the background, its result is never read, and the expensive
    # generation call below never happens. On a miss the same vector later
    # populates the cache.
    # Pass diagnostics into retrieval only when a caller opted in, so the seam
    # keeps its (query, k[, vector]) shape for callers/tests that don't care.
    retr_diag: dict = {}
    retr_kwargs = {"diagnostics": retr_diag} if diagnostics is not None else {}
    vector: list[float] | None = None
    if settings.rag_query_cache_enabled:
        cached = query_cache.get_exact(retrieval_query, k)
        if cached is not None:
            return cached
        vector = embeddings.embed_query(retrieval_query)
        future = _executor().submit(
            retrieve.retrieve, retrieval_query, k, vector=vector, **retr_kwargs
        )
        cached = query_cache.get_semantic(vector, k)
        if cached is not None:
            future.cancel()
            return cached
        # Miss: TEI/DB exceptions re-raise here exactly as they did inline.
        chunks = future.result()
    else:
        chunks = retrieve.retrieve(retrieval_query, k, **retr_kwargs)

    top_similarity = retr_diag.get("top_similarity")

    def _diag(coverage: str) -> None:
        if diagnostics is not None:
            diagnostics.update(
                coverage=coverage,
                chunks_retrieved=len(chunks),
                top_similarity=top_similarity,
            )

    if not chunks:
        # Nothing retrieved: answering would mean answering from the model's own
        # knowledge, which is exactly what this product must not do.
        _diag("no_match")
        return {"answer": NO_MATCH_AR, "sources": []}

    response = _client().messages.create(
        model=settings.answer_model,
        max_tokens=settings.answer_max_tokens,
        # Sonnet runs adaptive thinking when `thinking` is omitted. This is grounded
        # extraction over short passages, so disable it rather than pay for it.
        thinking={"type": "disabled"},
        output_config={"effort": settings.answer_effort},
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                # Caches once the prompt clears the minimum cacheable prefix; a no-op
                # (and no extra cost) while it is short. The per-question documents
                # correctly sit after it, so they never invalidate this prefix.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            *(_history_messages(history) if history else []),
            {
                "role": "user",
                "content": [*_documents(chunks), {"type": "text", "text": query_ar}],
            }
        ],
    )

    usage = response.usage
    logger.info(
        "RAG answer: model=%s chunks=%d in=%s out=%s cache_read=%s cache_write=%s",
        settings.answer_model,
        len(chunks),
        usage.input_tokens,
        usage.output_tokens,
        getattr(usage, "cache_read_input_tokens", 0),
        getattr(usage, "cache_creation_input_tokens", 0),
    )

    if response.stop_reason == "refusal":
        # Content may be empty or partial on a refusal — never read it as an answer.
        logger.warning("answer generation refused")
        _diag("refused")
        return {"answer": REFUSED_AR, "sources": []}

    text = "".join(block.text for block in response.content if block.type == "text")
    result = {"answer": text.strip() or NO_MATCH_AR, "sources": _sources(response.content, chunks)}
    _diag(_coverage(chunks, result["sources"], top_similarity))
    # Only cited answers are cache-worthy: empty sources means NO_MATCH (a KB gap
    # the nightly ingest may fill — caching would amplify it) or an uncited reply.
    if settings.rag_query_cache_enabled and result["sources"]:
        query_cache.put(retrieval_query, vector, k, result)
    return result
