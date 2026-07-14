"""Retry policy and fallback to a human agent.

Module: Telephony & Call Orchestration (requirements doc §2 "Call Orchestration":
retry logic, fall-back to human agent if AI fails).
"""

MAX_ATTEMPTS = 3


def should_retry(outcome: str, attempts: int) -> bool:
    """Decide whether a no-answer/failed call gets re-queued (workers.tasks)."""
    raise NotImplementedError


def transfer_to_agent(provider_call_sid: str) -> None:
    """Bridge the live call to a human agent when the AI can't proceed
    (customer says لا / غير متأكد repeatedly, asks for an agent, or STT fails)."""
    raise NotImplementedError
