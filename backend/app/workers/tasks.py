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

    Sprint 2/3: pulls rows sitting in call_logs with status == 'queued' — this covers
    both brand-new follow-ups and retry rows created by should_retry (Sprint 3), since
    both start life as 'queued'.
    Sprint 4 will replace the "already sitting in call_logs" part with a real CRM fetch.
    """
    from app.data.db import SessionLocal
    from app.data.models import CallLog

    with SessionLocal() as db:
        pending = db.query(CallLog).filter(CallLog.status == "queued").all()
        for row in pending:
            place_outbound_call.delay(row.id)
        logger.info("schedule_follow_up_batch: enqueued %d call(s)", len(pending))


@celery_app.task
def place_outbound_call(call_id: int) -> None:
    """Dial one customer (telephony.client) and record the attempt.
    Retries on no-answer/failure per telephony.call_flow.should_retry (Sprint 3) —
    a retry creates a NEW CallLog row (parent_call_log_id set, attempt_number + 1),
    it does not reuse this row, since provider_call_sid is now unique per row.
    """
    from datetime import UTC, datetime

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
        row.status = "initiated"
        row.started_at = datetime.now(UTC)
        db.commit()
        logger.info(
            "place_outbound_call: call_id=%s dialed, sid=%s, attempt_number=%d",
            row.id, call_sid, row.attempt_number,
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
                db.rollback()  # clear the failed txn so the rest of the batch survives
                logger.exception("KB ingest failed for doc %s — continuing batch", doc_id)
        if processed:
            # Close the loop: gaps the freshly-ingested docs now cover are auto-resolved.
            try:
                from app.data import kb_gaps

                closed = kb_gaps.recheck_open_gaps(db)
                logger.info("nightly ingest: auto-resolved %d KB gap(s) now covered", closed)
            except Exception:
                db.rollback()
                logger.exception("KB gap recheck after ingest failed")
    return processed


@celery_app.task
def generate_fcr_report(days: int = 7) -> int:
    """Compile and persist the 'First Call Resolutions' report for the last `days`.

    Idempotent per whole-day window — the nightly run refreshes one FCRReport row.
    Returns the report id.
    """
    from app.data import reporting
    from app.data.db import SessionLocal

    with SessionLocal() as db:
        report = reporting.generate_recent_fcr_report(db, days=days)
        logger.info("generate_fcr_report: report_id=%s fcr_rate=%s", report.id, report.fcr_rate)
        return report.id
