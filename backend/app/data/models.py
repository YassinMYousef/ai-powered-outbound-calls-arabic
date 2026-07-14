"""Database models — call logs + knowledge-base document storage.

Module: Backend/Data. These schemas unblock the telephony CRM link and the
RAG storage link; change them via Alembic migrations (backend/alembic/).
"""
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Must match settings.embedding_dimensions and the 0001 migration — changing the
# embedding model's dimension means a new migration plus a full re-ingest.
EMBEDDING_DIM = 1024


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
