"""Retry policy and fallback to a human agent.
Module: Telephony & Call Orchestration (requirements doc §2 "Call Orchestration":
retry logic, fall-back to human agent if AI fails).
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3

# Statuses that represent a call that never really connected/completed a
# conversation — these are worth retrying. "completed" always means the call
# was answered and ran through, even if the outcome was unresolved/transferred,
# so it is deliberately excluded from retry.
_RETRYABLE_STATUSES = {"no_answer", "busy", "failed"}


def should_retry(status: str, attempt_number: int) -> bool:
    """Decide whether a no-answer/failed call gets re-queued (workers.tasks).

    Only statuses in _RETRYABLE_STATUSES are retried, and only while the
    current attempt_number is still below MAX_ATTEMPTS.
    """
    return status in _RETRYABLE_STATUSES and attempt_number < MAX_ATTEMPTS


def transfer_to_agent(provider_call_sid: str) -> None:
    """Bridge the live call to a human agent when the AI can't proceed
    (customer says لا / غير متأكد repeatedly, asks for an agent, or STT fails).

    Delegates the Twilio call-update API to telephony.client, which owns all
    direct Twilio SDK usage.
    """
    if not settings.human_agent_number:
        raise RuntimeError("HUMAN_AGENT_NUMBER must be set to transfer calls")

    from app.telephony import client

    client.transfer_to_agent(provider_call_sid, settings.human_agent_number)
    logger.info("transfer_to_agent: call_sid=%s redirected to human agent", provider_call_sid)
