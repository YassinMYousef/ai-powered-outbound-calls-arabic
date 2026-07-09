"""Branching dialog tree for the follow-up call script.

Module: Conversation/NLU. The script pulls in details from the prior inbound
call (ticket ID, procedure steps) and branches on the customer's Arabic reply.
"""
from dataclasses import dataclass
from enum import Enum


class Intent(str, Enum):
    YES = "yes"              # "نعم" — procedure step completed
    NO = "no"                # "لا" — not completed
    UNCERTAIN = "uncertain"  # "غير متأكد"
    AGENT = "agent"          # customer asks for a live agent


class Action(str, Enum):
    MARK_RESOLVED = "mark_resolved"
    OFFER_HELP = "offer_help"
    TRANSFER_TO_AGENT = "transfer_to_agent"
    REPEAT_QUESTION = "repeat_question"
    END_CALL = "end_call"


@dataclass
class DialogState:
    call_id: int
    ticket_id: str | None = None
    turn: int = 0


def classify_intent(transcript_ar: str) -> Intent:
    """Map raw Arabic STT output to an Intent."""
    raise NotImplementedError


def next_action(state: DialogState, intent: Intent) -> Action:
    """Advance the dialog tree one turn. Called from telephony/webhooks.py."""
    raise NotImplementedError
