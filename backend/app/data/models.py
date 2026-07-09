"""Database models — call logs + knowledge-base document storage.

Module: Backend/Data. These schemas unblock the telephony CRM link and the
RAG storage link; change them via Alembic migrations once those exist.
"""
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_phone: Mapped[str] = mapped_column(String(20))
    ticket_id: Mapped[str | None] = mapped_column(String(64))  # from the prior inbound call
    provider_call_sid: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str | None] = mapped_column(String(32))  # resolved / unresolved / transferred / no_answer
    duration_seconds: Mapped[int | None]
    transcript: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KBDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    source_uri: Mapped[str | None] = mapped_column(String(512))  # original PDF/Wiki location
    content: Mapped[str | None] = mapped_column(Text)  # extracted text
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # last vector-DB sync
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
