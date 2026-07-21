"""Celery application — Redis broker/backend.

Run a worker (from backend/):  celery -A app.workers.celery_app worker --loglevel=info
Scheduled tasks need beat too:  celery -A app.workers.celery_app beat --loglevel=info
"""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery("callcenter", broker=settings.redis_url, backend=settings.redis_url)
celery_app.autodiscover_tasks(["app.workers"])

celery_app.conf.beat_schedule = {
    "nightly-kb-ingest": {
        "task": "app.workers.tasks.ingest_kb_documents",
        "schedule": crontab(hour=3, minute=0),
    },
    # Compiles the prior week's "First Call Resolutions" report for the quality
    # team every morning (idempotent per whole-day window).
    "nightly-fcr-report": {
        "task": "app.workers.tasks.generate_fcr_report",
        "schedule": crontab(hour=4, minute=0),
    },
}
