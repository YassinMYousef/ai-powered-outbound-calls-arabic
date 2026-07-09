"""Agent-facing RAG chatbot endpoint, consumed by the frontend ChatWidget.

Module: Conversation/NLU & RAG. Answers must be in Arabic and cite KB sources.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ChatQuery(BaseModel):
    query: str  # Arabic question from the agent


@router.post("/query")
def query(body: ChatQuery) -> dict:
    """Return {"answer": <Arabic answer>, "sources": [...]} from the internal KB.

    Delegates to app/conversation/rag/answer.py.
    """
    raise HTTPException(status_code=501, detail="Not implemented — see app/conversation/rag/answer.py")
