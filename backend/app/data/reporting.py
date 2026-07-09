"""KPI queries and the auto-generated "First Call Resolutions" report.

Module: Backend/Data & Reporting.
Targets (requirements doc §5): FCR rate ≥ 90%, time-to-answer < 2s for the
chatbot; AHT and completion % are compared against the live-agent baseline.
"""
from sqlalchemy.orm import Session


def fcr_rate(db: Session) -> float:
    """% of follow-up calls resolved on the first outbound attempt."""
    raise NotImplementedError


def completion_rate(db: Session) -> float:
    """% of calls fully handled by the AI without human handoff."""
    raise NotImplementedError


def average_handle_time(db: Session) -> float:
    """Mean call duration in seconds."""
    raise NotImplementedError


def generate_fcr_report(db: Session) -> str:
    """Compile resolved calls into the formatted 'First Call Resolutions'
    article for the quality team."""
    raise NotImplementedError
