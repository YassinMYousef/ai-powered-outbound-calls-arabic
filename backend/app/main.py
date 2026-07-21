"""FastAPI entry point — wires all module routers together.

Run locally (from backend/):  uvicorn app.main:app --reload
Interactive docs at http://localhost:8000/docs
"""
import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request

from app.api import agents, auth, calls, chat, customers, kb, reports
from app.logging_config import configure_logging, request_id_context
from app.telephony import webhooks

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    logger.info("application started")
    yield
    logger.info("application stopped")


app = FastAPI(title="CallCenter API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def log_request(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    token = request_id_context.set(request_id)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request failed", extra={"method": request.method, "path": request.url.path})
        raise
    else:
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request completed method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started_at) * 1000,
        )
        return response
    finally:
        request_id_context.reset(token)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(calls.router, prefix="/api/calls", tags=["calls"])
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(kb.router, prefix="/api/kb", tags=["knowledge-base"])
app.include_router(webhooks.router, prefix="/telephony", tags=["telephony-webhooks"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
