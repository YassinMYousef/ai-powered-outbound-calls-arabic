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
    """Fetch customers flagged for follow-up and enqueue one place_outbound_call per customer.

    Sprint 2: pulls rows already sitting in call_logs (outcome IS NULL, attempts == 0).
    Sprint 4 will replace this with a real CRM API fetch instead.
    """
    from app.data.db import SessionLocal
    from app.data.models import CallLog

    with SessionLocal() as db:
        pending = (
            db.query(CallLog)
            .filter(CallLog.outcome.is_(None), CallLog.attempts == 0)
            .all()
        )
        for row in pending:
            place_outbound_call.delay(row.id)
        logger.info("schedule_follow_up_batch: enqueued %d call(s)", len(pending))


@celery_app.task
def place_outbound_call(call_id: int) -> None:
    """Dial one customer (telephony.client) and record the attempt.
    Retries on no-answer/failure per telephony.call_flow.should_retry (added Sprint 3).
    """
    from app.data.db import SessionLocal
    from app.data.models import CallLog
    from app.telephony.client import place_call

    with SessionLocal() as db:
        row = db.get(CallLog, call_id)
        if row is None:
            logger.error("place_outbound_call: no CallLog row with id=%s", call_id)
            return

        call_sid = place_call(to_number=row.customer_phone, call_id=row.id)
        row.provider_call_sid = call_sid
        row.attempts += 1
        db.commit()
        logger.info(
            "place_outbound_call: call_id=%s dialed, sid=%s, attempt=%d",
            row.id, call_sid, row.attempts,
        )


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
