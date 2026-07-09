"""Celery application — Redis broker/backend.

Run a worker (from backend/):  celery -A app.workers.celery_app worker --loglevel=info
"""
from celery import Celery

from app.config import settings

celery_app = Celery("callcenter", broker=settings.redis_url, backend=settings.redis_url)
celery_app.autodiscover_tasks(["app.workers"])
