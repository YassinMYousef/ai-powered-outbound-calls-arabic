import anthropic
import httpx
import pytest

from app.api import chat
from app.data.models import ChatMessage, ChatSession, UnansweredQuestion

ANSWER = {
    "answer": "ادخل إلى النظام الداخلي واضغط تعديل.",
    "sources": [
        {
            "doc_id": 7,
            "title": "دليل العمليات",
            "source_uri": "ops.md",
            "chunk_index": 3,
            "score": 0.91,
            "quotes": ["ادخل إلى النظام الداخلي"],
        }
    ],
}


def _api_error() -> anthropic.APIError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(message="boom", request=request)


def test_first_turn_creates_session_and_persists_both_rows(client, db_session, monkeypatch) -> None:
    seen: dict = {}

    def fake_answer(query_ar: str, top_k=None, history=None, diagnostics=None):
        seen["query"], seen["top_k"], seen["history"] = query_ar, top_k, history
        return ANSWER

    monkeypatch.setattr(chat.answer_module, "answer", fake_answer)

    response = client.post("/api/chat/query", json={"query": "كيف أحدث بيانات العميل؟", "top_k": 3})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["session_id"], int)
    assert {k: body[k] for k in ("answer", "sources")} == ANSWER
    assert seen == {"query": "كيف أحدث بيانات العميل؟", "top_k": 3, "history": []}

    rows = db_session.query(ChatMessage).order_by(ChatMessage.id).all()
    assert [(r.role, r.content) for r in rows] == [
        ("user", "كيف أحدث بيانات العميل؟"),
        ("assistant", ANSWER["answer"]),
    ]
    assert rows[1].sources == ANSWER["sources"]
    assert rows[1].latency_ms >= 0
    assert db_session.query(ChatSession).count() == 1


def test_second_turn_reuses_session_and_replays_history(client, db_session, monkeypatch) -> None:
    seen: dict = {}

    def fake_answer(query_ar: str, top_k=None, history=None, diagnostics=None):
        seen["history"] = history
        return ANSWER

    monkeypatch.setattr(chat.answer_module, "answer", fake_answer)

    first = client.post("/api/chat/query", json={"query": "سؤال أول"}).json()
    response = client.post(
        "/api/chat/query", json={"query": "وبعد كده؟", "session_id": first["session_id"]}
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == first["session_id"]
    assert seen["history"] == [
        {"role": "user", "content": "سؤال أول"},
        {"role": "assistant", "content": ANSWER["answer"]},
    ]
    assert db_session.query(ChatSession).count() == 1
    assert db_session.query(ChatMessage).count() == 4


def test_unknown_session_is_404_and_persists_nothing(client, db_session, monkeypatch) -> None:
    def explode(query_ar: str, top_k=None, history=None, diagnostics=None):
        raise AssertionError("answer must not run for an unknown session")

    monkeypatch.setattr(chat.answer_module, "answer", explode)

    response = client.post("/api/chat/query", json={"query": "سؤال", "session_id": 9999})

    assert response.status_code == 404
    assert db_session.query(ChatSession).count() == 0
    assert db_session.query(ChatMessage).count() == 0


@pytest.mark.parametrize(
    "body",
    [{"query": ""}, {}, {"query": "سؤال", "top_k": 0}, {"query": "سؤال", "session_id": 0}],
)
def test_invalid_body_is_422(client, body) -> None:
    assert client.post("/api/chat/query", json=body).status_code == 422


def test_cached_answer_is_served_and_still_persists_the_turn(
    client, db_session, monkeypatch
) -> None:
    # Below the usual answer seam: with the cache enabled and L0 hitting,
    # retrieval and the LLM must never run, yet the turn is still a normal
    # conversation turn — persisted with sources and latency.
    from app.config import settings

    def explode(*args, **kwargs):
        raise AssertionError("retrieval/LLM must not run on a cache hit")

    monkeypatch.setattr(settings, "rag_query_cache_enabled", True)
    monkeypatch.setattr(chat.answer_module.query_cache, "get_exact", lambda q, k: ANSWER)
    monkeypatch.setattr(chat.answer_module.retrieve, "retrieve", explode)
    monkeypatch.setattr(chat.answer_module, "_client", explode)

    response = client.post("/api/chat/query", json={"query": "كيف أحدث بيانات العميل؟"})

    assert response.status_code == 200
    body = response.json()
    assert {k: body[k] for k in ("answer", "sources")} == ANSWER
    rows = db_session.query(ChatMessage).order_by(ChatMessage.id).all()
    assert [(r.role, r.content) for r in rows] == [
        ("user", "كيف أحدث بيانات العميل؟"),
        ("assistant", ANSWER["answer"]),
    ]
    assert rows[1].sources == ANSWER["sources"]
    assert rows[1].latency_ms >= 0


def test_missing_provider_key_is_503(client, monkeypatch) -> None:
    def boom(query_ar: str, top_k=None, history=None, diagnostics=None):
        raise RuntimeError("ANTHROPIC_API_KEY must be set for RAG answer generation")

    monkeypatch.setattr(chat.answer_module, "answer", boom)
    response = client.post("/api/chat/query", json={"query": "سؤال"})

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" not in response.text  # never leak config detail to the agent UI


def test_provider_failure_is_502_and_rolls_back_the_session(client, db_session, monkeypatch) -> None:
    def boom(query_ar: str, top_k=None, history=None, diagnostics=None):
        raise _api_error()

    monkeypatch.setattr(chat.answer_module, "answer", boom)

    assert client.post("/api/chat/query", json={"query": "سؤال"}).status_code == 502
    # The just-created session was only flushed; the rollback must drop it so
    # failed turns leave no empty sessions or dangling unanswered questions.
    assert db_session.query(ChatSession).count() == 0
    assert db_session.query(ChatMessage).count() == 0
    assert db_session.query(UnansweredQuestion).count() == 0


# --- unanswered-question (KB gap) logging ----------------------------------


def _answer_with_coverage(coverage: str, sources: list, *, chunks=0, sim=None):
    """A fake answer() that reports `coverage` through the diagnostics out-param,
    exactly as the real one does — so chat.py's gap-logging branch is exercised."""

    def fake_answer(query_ar: str, top_k=None, history=None, diagnostics=None):
        if diagnostics is not None:
            diagnostics.update(
                coverage=coverage, chunks_retrieved=chunks, top_similarity=sim
            )
        text = "لا توجد معلومات." if not sources else "إجابة."
        return {"answer": text, "sources": sources}

    return fake_answer


def test_uncovered_question_is_logged_as_a_gap_with_the_turn(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        chat.answer_module, "answer", _answer_with_coverage("no_match", [], chunks=0)
    )

    body = client.post("/api/chat/query", json={"query": "سؤال خارج قاعدة المعرفة"}).json()

    gaps = db_session.query(UnansweredQuestion).all()
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.query == "سؤال خارج قاعدة المعرفة"
    assert gap.reason == "no_match"
    assert gap.status == "open"
    assert gap.chunks_retrieved == 0
    assert gap.session_id == body["session_id"]
    # The turn itself is still persisted normally — a "not covered" reply is a turn.
    assert db_session.query(ChatMessage).count() == 2


def test_low_confidence_answer_is_logged_with_its_similarity(client, db_session, monkeypatch) -> None:
    weak_sources = [{"doc_id": 3, "title": "t", "source_uri": None, "chunk_index": 0,
                     "score": 0.01, "quotes": ["ن"]}]
    monkeypatch.setattr(
        chat.answer_module,
        "answer",
        _answer_with_coverage("low_confidence", weak_sources, chunks=4, sim=0.71),
    )

    client.post("/api/chat/query", json={"query": "سؤال ضعيف التغطية"})

    gap = db_session.query(UnansweredQuestion).one()
    assert gap.reason == "low_confidence"
    assert gap.chunks_retrieved == 4
    assert gap.top_similarity == 0.71


def test_covered_answer_records_no_gap(client, db_session, monkeypatch) -> None:
    good_sources = [{"doc_id": 7, "title": "t", "source_uri": "ops.md", "chunk_index": 3,
                     "score": 0.03, "quotes": ["ن"]}]
    monkeypatch.setattr(
        chat.answer_module,
        "answer",
        _answer_with_coverage("covered", good_sources, chunks=5, sim=0.93),
    )

    client.post("/api/chat/query", json={"query": "سؤال مغطى"})

    assert db_session.query(UnansweredQuestion).count() == 0
    assert db_session.query(ChatMessage).count() == 2


def test_cache_hit_sets_no_coverage_so_no_gap(client, db_session, monkeypatch) -> None:
    # A query-cache hit returns before diagnostics is populated; chat.py must read
    # the absence of a coverage verdict as "not a gap", not crash on the missing key.
    from app.config import settings

    def explode(*args, **kwargs):
        raise AssertionError("retrieval/LLM must not run on a cache hit")

    monkeypatch.setattr(settings, "rag_query_cache_enabled", True)
    monkeypatch.setattr(chat.answer_module.query_cache, "get_exact", lambda q, k: ANSWER)
    monkeypatch.setattr(chat.answer_module.retrieve, "retrieve", explode)
    monkeypatch.setattr(chat.answer_module, "_client", explode)

    client.post("/api/chat/query", json={"query": "كيف أحدث بيانات العميل؟"})

    assert db_session.query(UnansweredQuestion).count() == 0
