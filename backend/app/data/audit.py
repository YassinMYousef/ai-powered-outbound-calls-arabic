"""Access audit trail — KB content is proprietary, so reads and actions get logged.

Module: Backend/Data. `record` writes one audit_logs row and commits it; call it
from an endpoint AFTER the guarded work so the trail reflects access that actually
happened. Never let audit failure take down the request it is recording.
"""
import logging

from sqlalchemy.orm import Session

from app.data.models import AuditLog

logger = logging.getLogger(__name__)


def record(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    detail: dict | None = None,
) -> None:
    """Append an audit row (e.g. action='chat.query', resource_type='chat_session').

    Best-effort: a logging failure is swallowed (and the session rolled back) so it
    can never convert a successful, already-committed action into a 500.
    """
    try:
        db.add(
            AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                detail=detail or {},
            )
        )
        db.commit()
    except Exception:
        logger.exception("failed to write audit log for action=%s", action)
        db.rollback()
