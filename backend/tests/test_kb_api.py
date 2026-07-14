import io

import docx
import pytest
from sqlalchemy import select

from app.api import kb
from app.data.models import KBDocument


@pytest.fixture
def enqueued(monkeypatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(kb, "_enqueue_ingest", calls.append)
    return calls


def test_upload_markdown_creates_document_and_enqueues(client, db_session, enqueued) -> None:
    response = client.post(
        "/api/kb/documents",
        files={"file": ("دليل-الإجراءات.md", "# الإجراءات\n\nحدث البيانات.".encode(), "text/markdown")},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending_embedding"
    assert body["title"] == "دليل-الإجراءات"

    doc = db_session.get(KBDocument, body["id"])
    assert "حدث البيانات." in doc.content
    assert doc.source_uri == "دليل-الإجراءات.md"
    assert enqueued == [doc.id]


def test_upload_docx(client, enqueued) -> None:
    document = docx.Document()
    document.add_paragraph("سياسة الاسترجاع")
    buffer = io.BytesIO()
    document.save(buffer)

    response = client.post(
        "/api/kb/documents", files={"file": ("policy.docx", buffer.getvalue(), "application/octet-stream")}
    )
    assert response.status_code == 202


def test_upload_unsupported_type_is_415(client, db_session, enqueued) -> None:
    response = client.post("/api/kb/documents", files={"file": ("virus.exe", b"MZ", "application/x-msdownload")})
    assert response.status_code == 415
    assert db_session.execute(select(KBDocument)).scalars().all() == []
    assert enqueued == []


def test_upload_empty_file_is_400(client, db_session, enqueued) -> None:
    response = client.post("/api/kb/documents", files={"file": ("empty.txt", b"   \n", "text/plain")})
    assert response.status_code == 400
    assert db_session.execute(select(KBDocument)).scalars().all() == []
    assert enqueued == []


def test_list_documents_shows_coverage_gap(client, enqueued) -> None:
    client.post("/api/kb/documents", files={"file": ("a.txt", "نص أول".encode(), "text/plain")})
    client.post("/api/kb/documents", files={"file": ("b.txt", "نص ثان".encode(), "text/plain")})

    response = client.get("/api/kb/documents")
    assert response.status_code == 200
    docs = response.json()
    assert len(docs) == 2
    assert docs[0]["id"] > docs[1]["id"]  # newest first
    for row in docs:
        assert set(row) == {"id", "title", "source_uri", "embedded_at", "created_at"}
        assert row["embedded_at"] is None  # not embedded yet — the coverage-KPI gap
