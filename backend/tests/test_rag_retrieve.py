from app.conversation.rag import embeddings, retrieve as retrieve_module, vectorstore
from app.conversation.rag.retrieve import retrieve

CONTRACT_KEYS = {"text", "score", "doc_id", "title", "chunk_index", "source_uri"}


def test_retrieve_returns_query_chunks_contract(monkeypatch) -> None:
    canned = [
        {
            "text": "يمكنك تحديث بيانات العميل عبر النظام الداخلي.",
            "score": 0.91,
            "doc_id": 7,
            "title": "دليل العمليات",
            "chunk_index": 3,
            "source_uri": "ops-guide.pdf",
        },
        {
            "text": "راجع قسم الإجراءات.",
            "score": 0.62,
            "doc_id": 2,
            "title": "الأسئلة الشائعة",
            "chunk_index": 0,
            "source_uri": None,
        },
    ]
    seen: dict = {}

    monkeypatch.setattr(embeddings, "embed_query", lambda q: seen.setdefault("query", q) and [0.1] or [0.1])

    def fake_query(db, embedding, top_k):
        seen["embedding"], seen["top_k"] = embedding, top_k
        return canned

    monkeypatch.setattr(vectorstore, "query_chunks", fake_query)

    results = retrieve("كيف أحدث بيانات العميل؟", top_k=2)

    assert results == canned
    assert seen["query"] == "كيف أحدث بيانات العميل؟"
    assert seen["embedding"] == [0.1]
    assert seen["top_k"] == 2
    for row in results:
        assert set(row) == CONTRACT_KEYS
    assert results[0]["score"] >= results[1]["score"]


def test_retrieve_default_top_k_is_5(monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(embeddings, "embed_query", lambda q: [0.0])
    monkeypatch.setattr(
        vectorstore, "query_chunks", lambda db, e, k: seen.setdefault("top_k", k) and [] or []
    )
    retrieve("سؤال")
    assert seen["top_k"] == 5


def test_embed_query_applies_e5_prefix(monkeypatch) -> None:
    captured: dict = {}

    def _fake(texts):
        captured["texts"] = texts
        return [[0.0]] * len(texts)

    monkeypatch.setattr(embeddings, "_embed", _fake)
    assert embeddings.embed_query("ما هي الخطوات؟") == [0.0]
    assert captured["texts"] == ["query: ما هي الخطوات؟"]


def test_retrieve_module_uses_shared_wrappers() -> None:
    # Guard against a refactor to `from x import y` imports, which would break
    # the monkeypatch seams above and the provider-swap convention.
    assert retrieve_module.embeddings is embeddings
    assert retrieve_module.vectorstore is vectorstore
