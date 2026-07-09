"""KB ingestion pipeline: extract text → chunk → embed → upsert to the vector DB.

Module: Conversation/RAG. Runs nightly via workers/tasks.py::ingest_kb_documents
and on demand when a document is uploaded through /api/kb/documents.
"""


def ingest_document(doc_id: int) -> int:
    """Process one KB document (from app.data.models.KBDocument).

    Returns the number of chunks embedded. Stamps KBDocument.embedded_at on
    success so the knowledge-coverage KPI can be computed.
    """
    raise NotImplementedError
