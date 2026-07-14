import anthropic
import httpx
import pytest

from app.api import chat

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


def test_query_returns_answer_with_sources(client, monkeypatch) -> None:
    seen: dict = {}

    def fake_answer(query_ar: str, top_k=None):
        seen["query"], seen["top_k"] = query_ar, top_k
        return ANSWER

    monkeypatch.setattr(chat.answer_module, "answer", fake_answer)

    response = client.post("/api/chat/query", json={"query": "كيف أحدث بيانات العميل؟", "top_k": 3})

    assert response.status_code == 200
    assert response.json() == ANSWER
    assert seen == {"query": "كيف أحدث بيانات العميل؟", "top_k": 3}


@pytest.mark.parametrize("body", [{"query": ""}, {}, {"query": "سؤال", "top_k": 0}])
def test_invalid_body_is_422(client, body) -> None:
    assert client.post("/api/chat/query", json=body).status_code == 422


def test_missing_provider_key_is_503(client, monkeypatch) -> None:
    def boom(query_ar: str, top_k=None):
        raise RuntimeError("ANTHROPIC_API_KEY must be set for RAG answer generation")

    monkeypatch.setattr(chat.answer_module, "answer", boom)
    response = client.post("/api/chat/query", json={"query": "سؤال"})

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" not in response.text  # never leak config detail to the agent UI


def test_provider_failure_is_502(client, monkeypatch) -> None:
    def boom(query_ar: str, top_k=None):
        raise _api_error()

    monkeypatch.setattr(chat.answer_module, "answer", boom)
    assert client.post("/api/chat/query", json={"query": "سؤال"}).status_code == 502
