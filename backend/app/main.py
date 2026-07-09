"""FastAPI entry point — wires all module routers together.

Run locally (from backend/):  uvicorn app.main:app --reload
Interactive docs at http://localhost:8000/docs
"""
from fastapi import FastAPI

from app.api import calls, chat, kb, reports
from app.telephony import webhooks

app = FastAPI(title="CallCenter API", version="0.1.0")

app.include_router(calls.router, prefix="/api/calls", tags=["calls"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(kb.router, prefix="/api/kb", tags=["knowledge-base"])
app.include_router(webhooks.router, prefix="/telephony", tags=["telephony-webhooks"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
