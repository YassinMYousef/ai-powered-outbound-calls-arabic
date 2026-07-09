"""Knowledge-base document management — upload docs and trigger (re-)ingestion.

Module: Backend/Data (storage) + Conversation/RAG (embedding pipeline).
Access is role-restricted once app/data/auth.py lands.
"""
from fastapi import APIRouter, HTTPException, UploadFile

router = APIRouter()


@router.post("/documents", status_code=202)
def upload_document(file: UploadFile) -> dict:
    """Store a KB document (PDF/Word/Wiki export) and enqueue embedding."""
    raise HTTPException(status_code=501, detail="Not implemented — see app/conversation/rag/ingest.py")


@router.get("/documents")
def list_documents() -> list[dict]:
    """List KB documents with their last-embedded timestamps (knowledge coverage KPI)."""
    raise HTTPException(status_code=501, detail="Not implemented")
