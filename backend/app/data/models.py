"""Database models for Sprint 1 call-log and knowledge-base storage."""
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
    source_uri: Mapped[str | None] = mapped_column(String(512), unique=True)
    storage_uri: Mapped[str | None] = mapped_column(String(512))
    source_checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    mime_type: Mapped[str | None] = mapped_column(String(127))
    content: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, server_default="{}")
    ingestion_status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", nullable=False
    )
    ingestion_error: Mapped[str | None] = mapped_column(Text)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    chunks: Mapped[list["KBChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class KBChunk(Base):
    """An ordered, citation-ready passage extracted from a knowledge-base document."""

    __tablename__ = "kb_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="ck_kb_chunks_index_nonnegative"),
        CheckConstraint("token_count IS NULL OR token_count >= 0", name="ck_kb_chunks_token_count_nonnegative"),
        CheckConstraint("page_number IS NULL OR page_number > 0", name="ck_kb_chunks_page_positive"),
        CheckConstraint(
            "character_end IS NULL OR character_start IS NULL OR character_end >= character_start",
            name="ck_kb_chunks_character_range",
        ),
        UniqueConstraint("document_id", "chunk_index", name="uq_kb_chunks_document_index"),
        Index("ix_kb_chunks_document_index", "document_id", "chunk_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    character_start: Mapped[int | None] = mapped_column(Integer)
    character_end: Mapped[int | None] = mapped_column(Integer)
    token_count: Mapped[int | None] = mapped_column(Integer)
    vector_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    document: Mapped[KBDocument] = relationship(back_populates="chunks")
