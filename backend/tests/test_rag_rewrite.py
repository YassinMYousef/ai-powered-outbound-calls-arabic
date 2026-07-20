from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.config import settings
from app.conversation.rag import rewrite as rewrite_module
from app.conversation.rag.rewrite import REWRITE_SYSTEM, rewrite_query

HISTORY = [
    {"role": "user", "content": "كيف أعيد تعيين كلمة مرور العميل؟"},
    {"role": "assistant", "content": "ادخل إلى النظام واضغط إعادة تعيين."},
]


def _response(text: str) -> SimpleNamespace:
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


@pytest.fixture
def fake_llm(monkeypatch):
    """Record the request and return a canned rewrite. No network, no key."""
    calls: list[dict] = []
    state = {"response": _response("سؤال مستقل"), "error": None}

    def create(**kwargs):
        calls.append(kwargs)
        if state["error"] is not None:
            raise state["error"]
        return state["response"]

    monkeypatch.setattr(
        rewrite_module, "_client", lambda: SimpleNamespace(messages=SimpleNamespace(create=create))
    )
    return SimpleNamespace(calls=calls, state=state)


def test_no_history_returns_raw_query_without_any_call(monkeypatch) -> None:
    def explode():
        raise AssertionError("rewrite must not touch the client on a first turn")

    monkeypatch.setattr(rewrite_module, "_client", explode)
    assert rewrite_query("سؤال", []) == "سؤال"


def test_rewrites_follow_up_to_standalone_question(fake_llm) -> None:
    fake_llm.state["response"] = _response("  كيف أفعّل الشريحة الجديدة؟ \n")
    assert rewrite_query("وبعد كده أعمل إيه؟", HISTORY) == "كيف أفعّل الشريحة الجديدة؟"


def test_request_shape(fake_llm) -> None:
    rewrite_query("وبعد كده؟", HISTORY)
    request = fake_llm.calls[0]

    assert request["model"] == settings.rewrite_model
    assert request["max_tokens"] == settings.rewrite_max_tokens
    assert request["system"] == REWRITE_SYSTEM
    assert request["messages"] == [*HISTORY, {"role": "user", "content": "وبعد كده؟"}]
    # Haiku rejects effort, and adaptive thinking would burn tokens on a one-liner.
    assert "thinking" not in request
    assert "output_config" not in request


def test_history_window_is_bounded(fake_llm, monkeypatch) -> None:
    monkeypatch.setattr(settings, "rewrite_history_max_messages", 2)
    long_history = [
        {"role": "user", "content": f"سؤال {i}"} if i % 2 == 0 else
        {"role": "assistant", "content": f"إجابة {i}"}
        for i in range(8)
    ]
    rewrite_query("وبعدين؟", long_history)
    messages = fake_llm.calls[0]["messages"]
    assert messages == [*long_history[-2:], {"role": "user", "content": "وبعدين؟"}]


def test_api_error_falls_back_to_raw_query(fake_llm) -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake_llm.state["error"] = anthropic.APIConnectionError(message="boom", request=request)
    assert rewrite_query("وبعد كده؟", HISTORY) == "وبعد كده؟"


def test_empty_response_falls_back_to_raw_query(fake_llm) -> None:
    fake_llm.state["response"] = _response("   ")
    assert rewrite_query("وبعد كده؟", HISTORY) == "وبعد كده؟"


def test_client_requires_a_key_and_import_stays_safe(monkeypatch) -> None:
    rewrite_module._client.cache_clear()
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        rewrite_module._client()
    rewrite_module._client.cache_clear()
