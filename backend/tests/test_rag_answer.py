from types import SimpleNamespace

import pytest

from app.config import settings
from app.conversation.rag import answer as answer_module
from app.conversation.rag import embeddings, query_cache, retrieve, rewrite
from app.conversation.rag.answer import NO_MATCH_AR, REFUSED_AR, answer

HISTORY = [
    {"role": "user", "content": "كيف أعيد تعيين كلمة مرور العميل؟"},
    {"role": "assistant", "content": "ادخل إلى النظام واضغط إعادة تعيين."},
]

CHUNKS = [
    {
        "text": "لتحديث بيانات العميل ادخل إلى النظام الداخلي واضغط تعديل.",
        "score": 0.91,
        "doc_id": 7,
        "title": "دليل العمليات",
        "chunk_index": 3,
        "source_uri": "ops.md",
    },
    {
        "text": "التحديث يظهر خلال ٢٤ ساعة.",
        "score": 0.72,
        "doc_id": 7,
        "title": "دليل العمليات",
        "chunk_index": 4,
        "source_uri": "ops.md",
    },
    {
        "text": "سياسة الاسترجاع خلال ١٤ يوم.",
        "score": 0.40,
        "doc_id": 9,
        "title": "الفواتير",
        "chunk_index": 0,
        "source_uri": None,
    },
]


def _citation(document_index: int, cited_text: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="char_location",
        cited_text=cited_text,
        document_index=document_index,
        start_char_index=0,
        end_char_index=len(cited_text),
    )


def _block(text: str, citations: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text, citations=citations)


def _response(content: list, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=20,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
    )


@pytest.fixture
def fake_llm(monkeypatch):
    """Record the request and return a canned response. No network, no key."""
    calls: list[dict] = []
    state = {"response": _response([_block("إجابة.")])}

    def create(**kwargs):
        calls.append(kwargs)
        return state["response"]

    monkeypatch.setattr(
        answer_module, "_client", lambda: SimpleNamespace(messages=SimpleNamespace(create=create))
    )
    monkeypatch.setattr(retrieve, "retrieve", lambda q, k: CHUNKS)
    return SimpleNamespace(calls=calls, state=state)


# --- request shape (what makes citations trustworthy) ----------------------


def test_each_chunk_becomes_its_own_cited_document(fake_llm) -> None:
    answer("كيف أحدث بيانات العميل؟")
    content = fake_llm.calls[0]["messages"][0]["content"]
    documents = [b for b in content if b["type"] == "document"]

    assert len(documents) == len(CHUNKS)  # per-chunk, so a citation resolves to one chunk
    for doc, chunk in zip(documents, CHUNKS):
        assert doc["citations"] == {"enabled": True}  # all-or-none: every doc must have it
        assert doc["source"] == {
            "type": "text",
            "media_type": "text/plain",
            "data": chunk["text"],
        }
        assert doc["title"] == chunk["title"]


def test_question_is_the_last_content_block(fake_llm) -> None:
    answer("كيف أحدث بيانات العميل؟")
    content = fake_llm.calls[0]["messages"][0]["content"]
    assert content[-1] == {"type": "text", "text": "كيف أحدث بيانات العميل؟"}


def test_structured_outputs_are_never_requested(fake_llm) -> None:
    # output_config.format + citations is a hard 400 from the API.
    answer("سؤال")
    assert "format" not in fake_llm.calls[0]["output_config"]


def test_cost_controls_are_on_the_request(fake_llm) -> None:
    answer("سؤال")
    request = fake_llm.calls[0]
    # Omitting `thinking` makes Sonnet think adaptively on every query — the single
    # biggest avoidable cost here.
    assert request["thinking"] == {"type": "disabled"}
    assert request["output_config"]["effort"] == settings.answer_effort
    assert request["model"] == settings.answer_model
    assert request["max_tokens"] == settings.answer_max_tokens
    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}


# --- answer + citation mapping --------------------------------------------


def test_answer_concatenates_text_blocks_in_order(fake_llm) -> None:
    fake_llm.state["response"] = _response(
        [_block("ادخل إلى النظام "), _block("ثم اضغط تعديل.", [_citation(0, "اضغط تعديل")])]
    )
    assert answer("سؤال")["answer"] == "ادخل إلى النظام ثم اضغط تعديل."


def test_sources_come_only_from_cited_chunks(fake_llm) -> None:
    fake_llm.state["response"] = _response(
        [_block("نص.", [_citation(0, "ادخل إلى النظام الداخلي")])]
    )
    sources = answer("سؤال")["sources"]

    assert len(sources) == 1  # chunks 1 and 2 were retrieved but not cited
    assert sources[0] == {
        "doc_id": 7,
        "title": "دليل العمليات",
        "source_uri": "ops.md",
        "chunk_index": 3,
        "score": 0.91,
        "quotes": ["ادخل إلى النظام الداخلي"],
    }


def test_sources_dedupe_and_collect_every_quote(fake_llm) -> None:
    fake_llm.state["response"] = _response(
        [
            _block("أ.", [_citation(0, "اقتباس أول")]),
            _block("ب.", [_citation(2, "اقتباس ثالث")]),
            _block("ج.", [_citation(0, "اقتباس ثانٍ"), _citation(0, "اقتباس أول")]),
        ]
    )
    sources = answer("سؤال")["sources"]

    assert [s["chunk_index"] for s in sources] == [3, 0]  # ordered by first citation
    assert sources[0]["quotes"] == ["اقتباس أول", "اقتباس ثانٍ"]  # deduped
    assert sources[1]["quotes"] == ["اقتباس ثالث"]


def test_out_of_range_citation_is_skipped_not_raised(fake_llm) -> None:
    fake_llm.state["response"] = _response(
        [_block("نص.", [_citation(99, "خارج النطاق"), _citation(1, "اقتباس صالح")])]
    )
    sources = answer("سؤال")["sources"]
    assert [s["chunk_index"] for s in sources] == [4]


def test_uncited_answer_returns_no_sources(fake_llm) -> None:
    fake_llm.state["response"] = _response([_block("لا توجد معلومات كافية.")])
    assert answer("سؤال")["sources"] == []


# --- conversation history --------------------------------------------------


def test_history_threads_before_the_document_turn(fake_llm, monkeypatch) -> None:
    monkeypatch.setattr(rewrite, "rewrite_query", lambda q, h: q)

    answer("وبعد كده أعمل إيه؟", history=HISTORY)
    messages = fake_llm.calls[0]["messages"]

    assert len(messages) == 3
    assert messages[0] == HISTORY[0]  # plain text, oldest first
    assert messages[1]["role"] == "assistant"
    # The final turn keeps the exact single-turn shape: documents + question.
    assert [b["type"] for b in messages[-1]["content"][:-1]] == ["document"] * len(CHUNKS)
    assert messages[-1]["content"][-1] == {"type": "text", "text": "وبعد كده أعمل إيه؟"}


def test_last_history_block_carries_cache_breakpoint(fake_llm, monkeypatch) -> None:
    # System + history is the stable prefix; marking its tail lets each turn
    # reuse the previous turn's cache while document blocks churn after it.
    monkeypatch.setattr(rewrite, "rewrite_query", lambda q, h: q)

    answer("وبعد كده؟", history=HISTORY)
    messages = fake_llm.calls[0]["messages"]

    assert messages[1]["content"] == [
        {
            "type": "text",
            "text": HISTORY[1]["content"],
            "cache_control": {"type": "ephemeral"},
        }
    ]
    assert isinstance(messages[0]["content"], str)  # only the last history block is marked


def test_rewritten_query_drives_retrieval_but_not_the_prompt(fake_llm, monkeypatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(rewrite, "rewrite_query", lambda q, h: "كيف أفعّل الشريحة الجديدة؟")
    monkeypatch.setattr(retrieve, "retrieve", lambda q, k: seen.append(q) or CHUNKS)

    answer("وبعد كده أعمل إيه؟", history=HISTORY)

    assert seen == ["كيف أفعّل الشريحة الجديدة؟"]  # retrieval sees the standalone form
    final_block = fake_llm.calls[0]["messages"][-1]["content"][-1]
    assert final_block["text"] == "وبعد كده أعمل إيه؟"  # the model sees the agent's words


def test_first_turn_never_calls_rewrite(fake_llm, monkeypatch) -> None:
    def explode(q, h):
        raise AssertionError("rewrite must not run without history")

    monkeypatch.setattr(rewrite, "rewrite_query", explode)
    answer("سؤال")
    answer("سؤال", history=[])
    assert len(fake_llm.calls) == 2


def test_no_history_request_shape_is_unchanged(fake_llm) -> None:
    answer("سؤال")
    messages = fake_llm.calls[0]["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"


# --- the paths that must never reach the model ----------------------------


def test_empty_retrieval_never_calls_the_llm(monkeypatch) -> None:
    monkeypatch.setattr(retrieve, "retrieve", lambda q, k: [])

    def explode():
        raise AssertionError("LLM must not be called when nothing was retrieved")

    monkeypatch.setattr(answer_module, "_client", explode)

    result = answer("سؤال خارج قاعدة المعرفة")
    assert result == {"answer": NO_MATCH_AR, "sources": []}


def test_refusal_returns_fallback_and_no_sources(fake_llm) -> None:
    fake_llm.state["response"] = _response([], stop_reason="refusal")
    assert answer("سؤال")== {"answer": REFUSED_AR, "sources": []}


def test_top_k_defaults_to_settings_and_is_overridable(monkeypatch) -> None:
    seen: list[int] = []
    monkeypatch.setattr(retrieve, "retrieve", lambda q, k: seen.append(k) or [])

    answer("سؤال")
    answer("سؤال", top_k=3)
    assert seen == [settings.rag_top_k, 3]


# --- two-level query cache --------------------------------------------------

CACHED = {"answer": "إجابة مخبأة.", "sources": [{"doc_id": 7, "quotes": ["اقتباس"]}]}


def _explode(message: str):
    def fail(*args, **kwargs):
        raise AssertionError(message)

    return fail


@pytest.fixture
def cache_on(monkeypatch):
    """Enable the cache with both levels missing and every seam recorded."""
    monkeypatch.setattr(settings, "rag_query_cache_enabled", True)
    seen: dict = {"puts": [], "embed_calls": 0}

    def fake_embed(query):
        seen["embed_calls"] += 1
        return [0.1]

    monkeypatch.setattr(embeddings, "embed_query", fake_embed)
    monkeypatch.setattr(query_cache, "get_exact", lambda q, k: None)
    monkeypatch.setattr(query_cache, "get_semantic", lambda v, k: None)
    monkeypatch.setattr(
        query_cache, "put", lambda q, v, k, r: seen["puts"].append((q, v, k, r))
    )
    monkeypatch.setattr(retrieve, "retrieve", lambda q, k, vector=None: CHUNKS)
    return seen


def test_l0_hit_returns_cached_and_touches_nothing_else(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rag_query_cache_enabled", True)
    monkeypatch.setattr(query_cache, "get_exact", lambda q, k: CACHED)
    monkeypatch.setattr(embeddings, "embed_query", _explode("no embedding on an L0 hit"))
    monkeypatch.setattr(retrieve, "retrieve", _explode("no retrieval on an L0 hit"))
    monkeypatch.setattr(answer_module, "_client", _explode("no LLM on an L0 hit"))

    assert answer("سؤال") == CACHED


def test_l1_hit_abandons_retrieval_result_and_never_calls_the_llm(cache_on, monkeypatch) -> None:
    monkeypatch.setattr(query_cache, "get_semantic", lambda v, k: CACHED)
    monkeypatch.setattr(answer_module, "_client", _explode("no LLM on an L1 hit"))

    assert answer("سؤال") == CACHED
    assert cache_on["puts"] == []  # a replayed answer is never re-cached


def test_miss_generates_then_populates_with_post_rewrite_query(
    fake_llm, cache_on, monkeypatch
) -> None:
    fake_llm.state["response"] = _response([_block("نص.", [_citation(0, "اقتباس")])])
    monkeypatch.setattr(rewrite, "rewrite_query", lambda q, h: "سؤال مستقل")

    result = answer("وبعد كده؟", history=HISTORY)

    assert len(fake_llm.calls) == 1  # generation ran — this was a genuine miss
    (query, vector, k, cached_result), = cache_on["puts"]
    assert query == "سؤال مستقل"  # keyed on the standalone form, not the raw follow-up
    assert vector == [0.1]
    assert k == settings.rag_top_k
    assert cached_result == result


def test_query_is_embedded_exactly_once_per_miss(fake_llm, cache_on) -> None:
    # One vector shared by the L1 lookup, retrieval, and the cache write.
    fake_llm.state["response"] = _response([_block("نص.", [_citation(0, "اقتباس")])])
    answer("سؤال")
    assert cache_on["embed_calls"] == 1


def test_uncited_answer_is_never_cached(fake_llm, cache_on) -> None:
    fake_llm.state["response"] = _response([_block("لا توجد معلومات كافية.")])
    answer("سؤال")
    assert cache_on["puts"] == []


def test_empty_retrieval_is_never_cached(cache_on, monkeypatch) -> None:
    monkeypatch.setattr(retrieve, "retrieve", lambda q, k, vector=None: [])
    monkeypatch.setattr(answer_module, "_client", _explode("no LLM without chunks"))

    assert answer("سؤال") == {"answer": NO_MATCH_AR, "sources": []}
    assert cache_on["puts"] == []


def test_disabled_cache_touches_no_cache_seam(fake_llm, monkeypatch) -> None:
    # The autouse fixture disables the flag: the pre-cache code path must run
    # without embedding separately or consulting any cache function.
    monkeypatch.setattr(query_cache, "get_exact", _explode("cache disabled"))
    monkeypatch.setattr(query_cache, "get_semantic", _explode("cache disabled"))
    monkeypatch.setattr(query_cache, "put", _explode("cache disabled"))
    monkeypatch.setattr(embeddings, "embed_query", _explode("retrieve embeds internally"))

    assert answer("سؤال")["answer"] == "إجابة."


# --- import safety ---------------------------------------------------------


def test_client_requires_a_key_and_import_stays_safe(monkeypatch) -> None:
    answer_module._client.cache_clear()
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        answer_module._client()
    answer_module._client.cache_clear()


def test_answer_module_uses_shared_retrieve_wrapper() -> None:
    # Guards the monkeypatch seams and the provider-swap convention.
    assert answer_module.retrieve is retrieve
    assert answer_module.rewrite is rewrite
    assert answer_module.query_cache is query_cache
    assert answer_module.embeddings is embeddings
