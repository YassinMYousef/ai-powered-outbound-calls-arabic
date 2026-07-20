from app.conversation.rag import embeddings, lexical, retrieve as retrieve_module, vectorstore
from app.conversation.rag.retrieve import retrieve

CONTRACT_KEYS = {"text", "score", "doc_id", "title", "chunk_index", "source_uri"}

CHUNK_A = {
    "text": "راجع قسم المرتجعات للتفاصيل الكاملة.",
    "doc_id": 2,
    "title": "الأسئلة الشائعة",
    "chunk_index": 0,
    "source_uri": None,
}
CHUNK_B = {
    "text": "يمكنك تحديث بيانات العميل عبر النظام الداخلي.",
    "doc_id": 7,
    "title": "دليل العمليات",
    "chunk_index": 3,
    "source_uri": "ops-guide.pdf",
}


def _patch_arms(monkeypatch, semantic: list[dict], corpus: list[dict], seen: dict | None = None):
    def fake_query(db, embedding, top_k):
        if seen is not None:
            seen["embedding"], seen["pool"] = embedding, top_k
        return [{**row, "score": 0.9} for row in semantic]

    monkeypatch.setattr(embeddings, "embed_query", lambda q: [0.1])
    monkeypatch.setattr(vectorstore, "query_chunks", fake_query)
    monkeypatch.setattr(vectorstore, "all_chunks", lambda db: corpus)


def test_chunk_found_by_both_arms_outranks_semantic_only(monkeypatch) -> None:
    # Semantic prefers A; BM25 only matches B (query terms appear in B's text).
    # RRF must promote B — agreement across arms beats one arm's top pick.
    _patch_arms(monkeypatch, semantic=[CHUNK_A, CHUNK_B], corpus=[CHUNK_A, CHUNK_B])

    results = retrieve("كيف أحدث بيانات العميل؟", top_k=2)

    assert [row["doc_id"] for row in results] == [7, 2]
    for row in results:
        assert set(row) == CONTRACT_KEYS
    assert results[0]["score"] > results[1]["score"]


def test_lexical_arm_rescues_chunk_semantic_missed(monkeypatch) -> None:
    # An exact error code the embedding arm whiffs on must still be retrievable.
    code_chunk = {
        "text": "رمز الخطأ E-450 يعني فشل تفعيل الشريحة.",
        "doc_id": 9,
        "title": "أكواد الأخطاء",
        "chunk_index": 1,
        "source_uri": "errors.md",
    }
    _patch_arms(monkeypatch, semantic=[], corpus=[CHUNK_A, code_chunk])

    results = retrieve("ما معنى E-450؟", top_k=5)

    assert [row["doc_id"] for row in results] == [9]
    assert set(results[0]) == CONTRACT_KEYS


def test_each_arm_overfetches_then_returns_top_k(monkeypatch) -> None:
    seen: dict = {}
    _patch_arms(monkeypatch, semantic=[CHUNK_A, CHUNK_B], corpus=[], seen=seen)

    results = retrieve("كيف أحدث بيانات العميل؟", top_k=1)

    assert seen["pool"] == 3  # top_k × candidate factor
    assert seen["embedding"] == [0.1]
    assert len(results) == 1


def test_retrieve_default_top_k_is_5(monkeypatch) -> None:
    seen: dict = {}
    _patch_arms(monkeypatch, semantic=[], corpus=[], seen=seen)
    assert retrieve("سؤال") == []
    assert seen["pool"] == 15


def test_precomputed_vector_skips_embedding_and_drives_the_semantic_arm(monkeypatch) -> None:
    # answer.py embeds once and shares the vector with the query cache.
    seen: dict = {}
    _patch_arms(monkeypatch, semantic=[], corpus=[], seen=seen)

    def explode(q):
        raise AssertionError("embed_query must not run when a vector is supplied")

    monkeypatch.setattr(embeddings, "embed_query", explode)

    assert retrieve("سؤال", top_k=1, vector=[0.5]) == []
    assert seen["embedding"] == [0.5]


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
    assert retrieve_module.lexical is lexical
