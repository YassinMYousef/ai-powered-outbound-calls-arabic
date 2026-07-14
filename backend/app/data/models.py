"""Database models — call logs + knowledge-base document storage.

Module: Backend/Data. These schemas unblock the telephony CRM link and the
RAG storage link; change them via Alembic migrations (backend/alembic/).
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

# Must match settings.embedding_dimensions and the 0001 migration — changing the
# embedding model's dimension means a new migration plus a full re-ingest.
EMBEDDING_DIM = 1024


class Base(DeclarativeBase):
    pass


class CallLog(Base):
    """One outbound-call attempt, including retries linked to their original attempt."""

    __tablename__ = "call_logs"
    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="ck_call_logs_attempt_number_positive"),
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="ck_call_logs_duration_nonnegative"),
        CheckConstraint(
            "status IN ('queued', 'initiated', 'ringing', 'in_progress', 'completed', "
            "'no_answer', 'busy', 'failed', 'cancelled')",
            name="ck_call_logs_status",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('resolved', 'unresolved', 'transferred', 'unknown')",
            name="ck_call_logs_outcome",
        ),
        Index("ix_call_logs_ticket_created", "ticket_id", "created_at"),
        Index("ix_call_logs_status_created", "status", "created_at"),
        Index("ix_call_logs_customer_created", "customer_phone", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_phone: Mapped[str] = mapped_column(String(20), index=True)
    # The inbound CRM is not part of this service, so this is an indexed external reference.
    ticket_id: Mapped[str | None] = mapped_column(String(64), index=True)
    parent_call_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("call_logs.id", ondelete="SET NULL"), index=True
    )
    provider_call_sid: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", server_default="queued")
    outcome: Mapped[str | None] = mapped_column(String(32))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    transcript: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    parent_call_log: Mapped["CallLog | None"] = relationship(
        remote_side="CallLog.id", back_populates="retry_attempts"
    )
    retry_attempts: Mapped[list["CallLog"]] = relationship(back_populates="parent_call_log")


class KBDocument(Base):
    """A source document queued for future extraction and vector indexing."""

    __tablename__ = "kb_documents"
    __table_args__ = (
        CheckConstraint(
            "ingestion_status IN ('pending', 'processing', 'ready', 'failed')",
            name="ck_kb_documents_ingestion_status",
        ),
        Index("ix_kb_documents_status_created", "ingestion_status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    source_uri: Mapped[str | None] = mapped_column(String(512))  # original PDF/Wiki location
    content: Mapped[str | None] = mapped_column(Text)  # extracted text
    content_hash: Mapped[str | None] = mapped_column(String(64))  # sha256 of content at last embed
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # last vector-DB sync
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KBChunk(Base):
    """One embedded chunk of a KB document — the vector store (pgvector).

    Replaced wholesale on re-ingest. The JSON variant keeps SQLite (tests)
    able to create/insert this table; similarity queries are Postgres-only.
    """

    __tablename__ = "kb_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite"))
