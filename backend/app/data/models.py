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


class Customer(Base):
    """A CRM customer record.

    The requirements doc's architecture diagram has a "[CRM / Inbound Call
    Records]" box with no real external system behind it — this table is
    that source of truth for this project: who to follow up with, and why
    (via `CallLog.ticket_id` on the calls flagged from here).
    """

    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("phone", name="uq_customers_phone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    call_logs: Mapped[list["CallLog"]] = relationship(back_populates="customer")


class Agent(Base):
    """A human agent on the outbound-calling team.

    Not an auth account — backend/app/data/auth.py's OAuth2/RBAC is still
    unimplemented (NotImplementedError), so this is a roster a manager
    maintains, not a login. Not linked to CallLog yet either; that's the
    natural next step (see docs/frontend-dashboard.md's Agent activity
    section) but a separate feature from "a manager can add agents."
    """

    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("email", name="uq_agents_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


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
    # Nullable: rows created before the customers table existed, or dialed ad hoc
    # (e.g. PlaceRealCallForm) without going through a CRM record, have none.
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    parent_call_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("call_logs.id", ondelete="SET NULL"), index=True
    )
    provider_call_sid: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", server_default="queued")
    outcome: Mapped[str | None] = mapped_column(String(32))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    transcript: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    # Retained from main's initial schema for existing call-flow compatibility.
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    customer: Mapped["Customer | None"] = relationship(back_populates="call_logs")
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
    source_uri: Mapped[str | None] = mapped_column(String(512))
    storage_uri: Mapped[str | None] = mapped_column(String(512))
    source_checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    mime_type: Mapped[str | None] = mapped_column(String(127))
    content: Mapped[str | None] = mapped_column(Text)
    # Retained because the current ingestion pipeline uses it to detect re-embedding work.
    content_hash: Mapped[str | None] = mapped_column(String(64))
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
    """One embedded chunk of a KB document — the vector store (pgvector).

    Replaced wholesale on re-ingest. The JSON variant keeps SQLite (tests)
    able to create/insert this table; similarity queries are Postgres-only.
    """

    __tablename__ = "kb_chunks"
    __table_args__ = (
        CheckConstraint("page_number IS NULL OR page_number > 0", name="ck_kb_chunks_page_positive"),
        CheckConstraint("token_count IS NULL OR token_count >= 0", name="ck_kb_chunks_token_count_nonnegative"),
        CheckConstraint(
            "character_end IS NULL OR character_start IS NULL OR character_end >= character_start",
            name="ck_kb_chunks_character_range",
        ),
        UniqueConstraint("document_id", "chunk_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int]
    # `text` and `embedding` are preserved for main's pgvector retrieval implementation.
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite"))
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
