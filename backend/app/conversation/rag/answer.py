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
from functools import lru_cache

from anthropic import Anthropic

from app.config import settings
from app.conversation.rag import retrieve

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
- Do not write source references inline; the system attaches the cited sources."""


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


def answer(query_ar: str, top_k: int | None = None) -> dict:
    """Answer an Arabic question from the KB, with the sources that back it.

    Returns:
        {
            "answer": str,        # Arabic (MSA)
            "sources": [          # only the passages actually cited, best first
                {
                    "doc_id": int,
                    "title": str,
                    "source_uri": str | None,
                    "chunk_index": int,
                    "score": float,        # retrieval similarity
                    "quotes": [str, ...],  # exact spans the answer rests on
                },
                ...
            ],
        }

    An empty `sources` list means the KB did not support an answer — the caller
    must treat the reply as "not covered", never as an uncited fact.
    """
    chunks = retrieve.retrieve(query_ar, top_k or settings.rag_top_k)
    if not chunks:
        # Nothing retrieved: answering would mean answering from the model's own
        # knowledge, which is exactly what this product must not do.
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
        return {"answer": REFUSED_AR, "sources": []}

    text = "".join(block.text for block in response.content if block.type == "text")
    return {"answer": text.strip() or NO_MATCH_AR, "sources": _sources(response.content, chunks)}
