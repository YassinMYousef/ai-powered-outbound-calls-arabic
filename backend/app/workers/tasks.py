"""Celery tasks — everything scheduled, queued, or retried lives here.

Modules: Telephony (call scheduling/retries), Conversation/RAG (nightly
ingestion), Backend/Data (report generation).
"""
from app.workers.celery_app import celery_app


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
def ingest_kb_documents() -> None:
    """Nightly: (re-)embed new or changed KB documents (conversation.rag.ingest)."""
    raise NotImplementedError


@celery_app.task
def generate_fcr_report() -> None:
    """Compile the 'First Call Resolutions' report (data.reporting)."""
    raise NotImplementedError
