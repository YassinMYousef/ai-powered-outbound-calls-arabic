import pytest
from sqlalchemy import select

from app.conversation.rag import embeddings, ingest
from app.data.models import KBChunk, KBDocument

# vectorstore.replace_doc_chunks runs for real against SQLite (JSON embedding
# variant) — only the embedding call is faked.


@pytest.fixture
def fake_embed(monkeypatch):
    calls: list[list[str]] = []

    def _fake(texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return [[float(i), 0.5] for i in range(len(texts))]

    monkeypatch.setattr(embeddings, "embed_passages", _fake)
    return calls


def _add_doc(db, content: str, title: str = "دليل الإجراءات") -> KBDocument:
    doc = KBDocument(title=title, source_uri=f"{title}.md", content=content)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def test_ingest_stores_chunks_and_stamps_document(db_session, fake_embed) -> None:
    doc = _add_doc(db_session, "الفقرة الأولى.\n\n" + "الفقرة الثانية الطويلة جدا. " * 100)
    count = ingest.ingest_document(doc.id, db=db_session)

    chunks = db_session.execute(
        select(KBChunk).where(KBChunk.document_id == doc.id).order_by(KBChunk.chunk_index)
    ).scalars().all()
    assert count == len(chunks) > 1
    assert [c.chunk_index for c in chunks] == list(range(count))
    assert fake_embed == [[c.text for c in chunks]]
    assert doc.embedded_at is not None
    assert doc.content_hash == ingest.content_sha256(doc.content)


def test_reingest_replaces_chunks_not_duplicates(db_session, fake_embed) -> None:
    doc = _add_doc(db_session, "نص " * 800)  # 2400 chars > rag_chunk_size → several chunks
    first = ingest.ingest_document(doc.id, db=db_session)
    doc.content = "نص قصير"
    db_session.commit()
    second = ingest.ingest_document(doc.id, db=db_session)

    remaining = db_session.execute(
        select(KBChunk).where(KBChunk.document_id == doc.id)
    ).scalars().all()
    assert first > 1 and second == 1
    assert len(remaining) == 1
    assert remaining[0].text == "نص قصير"


def test_empty_document_stamps_and_stores_nothing(db_session, fake_embed) -> None:
    doc = _add_doc(db_session, "")
    assert ingest.ingest_document(doc.id, db=db_session) == 0
    assert fake_embed == []  # no embedding call for zero chunks
    assert doc.embedded_at is not None
    assert db_session.execute(select(KBChunk)).scalars().all() == []


def test_missing_document_raises(db_session) -> None:
    with pytest.raises(ValueError, match="999"):
        ingest.ingest_document(999, db=db_session)


def test_docs_needing_embedding_change_detection(db_session, fake_embed) -> None:
    doc = _add_doc(db_session, "المحتوى الأصلي")
    assert ingest.docs_needing_embedding(db_session) == [doc.id]  # never embedded

    ingest.ingest_document(doc.id, db=db_session)
    assert ingest.docs_needing_embedding(db_session) == []  # up to date

    doc.content = "محتوى معدل"
    db_session.commit()
    assert ingest.docs_needing_embedding(db_session) == [doc.id]  # content edited


def test_ingest_invalidates_the_query_cache(db_session, fake_embed, monkeypatch) -> None:
    # A cached chat answer may cite the pre-change KB, so every successful
    # ingest must flush both cache levels (after commit).
    calls: list[bool] = []
    monkeypatch.setattr(ingest.query_cache, "invalidate_all", lambda: calls.append(True))

    doc = _add_doc(db_session, "محتوى المستند")
    ingest.ingest_document(doc.id, db=db_session)

    assert calls == [True]


def test_failed_ingest_does_not_invalidate_the_query_cache(db_session, monkeypatch) -> None:
    def explode():
        raise AssertionError("a failed ingest must not flush a still-valid cache")

    monkeypatch.setattr(ingest.query_cache, "invalidate_all", explode)
    with pytest.raises(ValueError):
        ingest.ingest_document(999, db=db_session)


def test_embed_passages_applies_e5_prefix(monkeypatch) -> None:
    captured: dict = {}

    def _fake(texts):
        captured["texts"] = texts
        return [[0.0]] * len(texts)

    monkeypatch.setattr(embeddings, "_embed", _fake)
    embeddings.embed_passages(["أول", "ثاني"])
    assert captured["texts"] == ["passage: أول", "passage: ثاني"]
