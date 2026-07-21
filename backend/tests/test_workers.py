from app.workers.celery_app import celery_app
from app.workers.tasks import ingest_kb_documents


def test_nightly_kb_ingest_is_scheduled() -> None:
    entry = celery_app.conf.beat_schedule["nightly-kb-ingest"]
    assert entry["task"] == "app.workers.tasks.ingest_kb_documents"


def test_nightly_batch_survives_one_bad_document(monkeypatch) -> None:
    class _FakeSession:
        def rollback(self) -> None:  # the batch rolls back a failed doc's txn
            pass

    class _FakeSessionContext:
        def __enter__(self):
            return _FakeSession()

        def __exit__(self, *exc):
            return False

    processed: list[int] = []

    def fake_ingest(doc_id: int, db=None) -> int:
        if doc_id == 2:
            raise RuntimeError("boom")
        processed.append(doc_id)
        return 1

    monkeypatch.setattr("app.data.db.SessionLocal", lambda: _FakeSessionContext())
    monkeypatch.setattr("app.conversation.rag.ingest.docs_needing_embedding", lambda db: [1, 2, 3])
    monkeypatch.setattr("app.conversation.rag.ingest.ingest_document", fake_ingest)
    # The post-ingest gap recheck needs retrieval/DB — out of scope for this unit.
    monkeypatch.setattr("app.data.kb_gaps.recheck_open_gaps", lambda db: 0)

    # Call the task body directly — no broker needed.
    assert ingest_kb_documents() == 2
    assert processed == [1, 3]


def test_worker_and_app_modules_import_without_providers() -> None:
    # Importing the app, tasks, and RAG modules must never require a DB,
    # Redis, TEI, or any API key (import-time safety convention).
    import app.conversation.rag.embeddings
    import app.conversation.rag.ingest
    import app.conversation.rag.retrieve
    import app.main
    import app.workers.tasks  # noqa: F401
