"""Database models — the full product schema.

Module: Backend/Data. Covers the call loop (call_logs, follow_up_tickets),
the RAG loop (kb_documents, kb_chunks, chat_sessions, chat_messages), and the
data/reporting surface (users + RBAC, fcr_reports, audit_logs); change them
via Alembic migrations (backend/alembic/).
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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


class RagQueryCache(Base):
    """One cached RAG answer keyed by its (post-rewrite) query embedding — the L1
    semantic level of the chat query cache (L0 exact lives in Redis).

    Rows expire by created_at cutoff (deleted opportunistically on write) and the
    whole table is flushed on KB ingestion. The JSON variant keeps SQLite (tests)
    able to create/insert this table; similarity lookups are Postgres-only.
    """

    __tablename__ = "rag_query_cache"
    __table_args__ = (
        CheckConstraint("top_k > 0", name="ck_rag_query_cache_top_k_positive"),
        Index("ix_rag_query_cache_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # The standalone retrieval query the answer was generated for (ops/debugging).
    query: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite"))
    top_k: Mapped[int] = mapped_column(Integer)
    # settings.answer_model at write time — a model change must never serve stale answers.
    model: Mapped[str] = mapped_column(String(64))
    # The exact {"answer": str, "sources": [...]} dict /api/chat/query returns.
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UnansweredQuestion(Base):
    """A chat question the KB could not answer — a knowledge gap for admins to fill.

    Recorded (inside the chat turn's own transaction, so a failed turn leaves none)
    whenever rag/answer.py produces no usable coverage. `reason` is that verdict:
    'no_match' (retrieval empty), 'no_citation' (passages retrieved but the grounded
    model cited none), or 'low_confidence' (an answer was cited but the best passage's
    raw cosine `top_similarity` was below settings.rag_gap_min_similarity).

    Rows are per-occurrence; `normalized_query` (Arabic-normalized via
    conversation/rag/lexical.tokenize) groups repeats so the review UI can rank gaps
    by how often agents hit them. Resolving a gap flips every open row sharing a
    normalized_query; a later occurrence just opens a fresh row, so a recurring gap
    resurfaces on its own.
    """

    __tablename__ = "unanswered_questions"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('no_match', 'no_citation', 'low_confidence')",
            name="ck_unanswered_questions_reason",
        ),
        CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')",
            name="ck_unanswered_questions_status",
        ),
        CheckConstraint(
            "chunks_retrieved IS NULL OR chunks_retrieved >= 0",
            name="ck_unanswered_questions_chunks_nonnegative",
        ),
        Index("ix_unanswered_questions_status_created", "status", "created_at"),
        Index("ix_unanswered_questions_normalized", "normalized_query"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(Text)  # the agent's original Arabic wording
    normalized_query: Mapped[str] = mapped_column(Text)  # Arabic-normalized grouping key
    reason: Mapped[str] = mapped_column(String(16))
    chunks_retrieved: Mapped[int | None] = mapped_column(Integer)
    # Raw cosine (0-1) of the best passage backing the answer; NULL when nothing
    # was cited. Kept for admin triage and to tune rag_gap_min_similarity.
    top_similarity: Mapped[float | None] = mapped_column(Float)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default="open", server_default="open", nullable=False
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)  # e.g. which doc was added
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class User(Base):
    """A dashboard/widget user — backs OAuth2 + RBAC in data/auth.py.

    Roles mirror frontend/src/auth/types.ts plus 'admin' for operations.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('agent', 'quality_manager', 'admin')",
            name="ck_users_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))  # Arabic display name
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="agent", server_default="agent")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")


class Customer(Base):
    """A customer we call for follow-ups — the local mirror of CRM contact data."""

    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "preferred_language IN ('ar-EG', 'ar')", name="ck_customers_preferred_language"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))  # Arabic
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[str | None] = mapped_column(String(255))
    governorate: Mapped[str | None] = mapped_column(String(64))  # Arabic
    # Egyptian colloquial vs MSA — steers TTS voice/register once selectable.
    preferred_language: Mapped[str] = mapped_column(
        String(8), default="ar-EG", server_default="ar-EG"
    )
    # External CRM identifier, same pattern as CallLog.ticket_id.
    crm_customer_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    follow_up_tickets: Mapped[list["FollowUpTicket"]] = relationship(back_populates="customer")


class FollowUpTicket(Base):
    """One CRM row flagged for an outbound follow-up call.

    This is the local copy of the CRM follow-up list that
    workers/tasks.schedule_follow_up_batch consumes; `crm_ticket_id` carries the
    same external identifier CallLog.ticket_id records, so the two link by value
    (the inbound CRM itself stays external — no FK). `customer_name`/
    `customer_phone` stay denormalized as the snapshot the CRM sent, even when
    the row also links to a `customers` record.
    """

    __tablename__ = "follow_up_tickets"
    __table_args__ = (
        CheckConstraint(
            "follow_up_status IN ('pending', 'queued', 'in_progress', 'resolved', "
            "'escalated', 'cancelled')",
            name="ck_follow_up_tickets_status",
        ),
        Index("ix_follow_up_tickets_status_created", "follow_up_status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crm_ticket_id: Mapped[str] = mapped_column(String(64), unique=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    customer_name: Mapped[str | None] = mapped_column(String(255))  # Arabic
    customer_phone: Mapped[str] = mapped_column(String(20), index=True)
    # What the prior inbound call asked the customer to do — feeds
    # speech/greeting.GreetingContext.procedure, so it is Arabic and verb-phrased.
    procedure: Mapped[str | None] = mapped_column(String(255))
    issue_summary: Mapped[str | None] = mapped_column(Text)
    inbound_call_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    customer: Mapped["Customer | None"] = relationship(back_populates="follow_up_tickets")


class ChatSession(Base):
    """One agent's conversation with the RAG chatbot (frontend ChatWidget)."""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable until OAuth2/RBAC guards /api/chat — anonymous sessions keep their history.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User | None"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )


class ChatMessage(Base):
    """One turn in a chat session; assistant turns carry their KB citations."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_messages_role"),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0", name="ck_chat_messages_latency_nonnegative"
        ),
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)  # Arabic
    # Citation payload as returned by rag/answer.py's "sources" list.
    sources: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    # Requirements doc §5 targets chatbot time-to-answer < 2s — measured per turn.
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class FCRReport(Base):
    """One generated 'First Call Resolutions' report for the quality team."""

    __tablename__ = "fcr_reports"
    __table_args__ = (
        CheckConstraint("period_end >= period_start", name="ck_fcr_reports_period"),
        CheckConstraint(
            "fcr_rate IS NULL OR (fcr_rate >= 0 AND fcr_rate <= 1)",
            name="ck_fcr_reports_fcr_rate_range",
        ),
        CheckConstraint(
            "completion_rate IS NULL OR (completion_rate >= 0 AND completion_rate <= 1)",
            name="ck_fcr_reports_completion_rate_range",
        ),
        # Nightly generation is idempotent per reporting window.
        UniqueConstraint("period_start", "period_end", name="uq_fcr_reports_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total_calls: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    resolved_first_attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    fcr_rate: Mapped[float | None] = mapped_column(Float)
    completion_rate: Mapped[float | None] = mapped_column(Float)
    average_handle_time_seconds: Mapped[float | None] = mapped_column(Float)
    # The formatted Arabic article data/reporting.generate_fcr_report compiles.
    report_markdown: Mapped[str | None] = mapped_column(Text)
    generated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditLog(Base):
    """Access audit trail — KB content is proprietary, so reads get logged too."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64))  # e.g. 'kb.read', 'chat.query', 'report.view'
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
