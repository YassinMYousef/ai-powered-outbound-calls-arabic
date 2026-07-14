"""Celery tasks — everything scheduled, queued, or retried lives here.

Modules: Telephony (call scheduling/retries), Conversation/RAG (nightly
ingestion), Backend/Data (report generation). Heavy imports stay inside task
bodies so importing this module never needs a DB or provider.
"""
import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def schedule_follow_up_batch() -> None:
    """Fetch customers flagged for follow-up (CRM / inbound call records) and
    enqueue one place_outbound_call per customer."""
    raise NotImplementedError


@celery_app.task
def place_outbound_call(call_id: int) -> None:
    """Dial one customer (telephony.client) and record the attempt.

    Retries on no-answer/failure per telephony.call_flow.should_retry.
    """
    raise NotImplementedError


@celery_app.task
def ingest_kb_document(doc_id: int) -> int:
    """Embed one KB document right away (enqueued best-effort on upload)."""
    from app.conversation.rag import ingest

    return ingest.ingest_document(doc_id)


@celery_app.task
def ingest_kb_documents() -> int:
    """Nightly: (re-)embed new or changed KB documents. Returns docs processed."""
    from app.conversation.rag import ingest
    from app.data.db import SessionLocal

    processed = 0
    with SessionLocal() as db:
        for doc_id in ingest.docs_needing_embedding(db):
            try:
                ingest.ingest_document(doc_id, db=db)
                processed += 1
            except Exception:
                logger.exception("KB ingest failed for doc %s — continuing batch", doc_id)
    return processed


@celery_app.task
def generate_fcr_report() -> None:
    """Compile the 'First Call Resolutions' report (data.reporting)."""
    raise NotImplementedError
