"""Create Sprint 1 call-log and knowledge-base storage tables.

Revision ID: 0001_sprint1_data_schema
Revises:
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_sprint1_data_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "call_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_phone", sa.String(length=20), nullable=False),
        sa.Column("ticket_id", sa.String(length=64)),
        sa.Column("parent_call_log_id", sa.Integer(), sa.ForeignKey("call_logs.id", ondelete="SET NULL")),
        sa.Column("provider_call_sid", sa.String(length=64), unique=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("outcome", sa.String(length=32)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("transcript", sa.Text()),
        sa.Column("failure_reason", sa.String(length=255)),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("attempt_number > 0", name="ck_call_logs_attempt_number_positive"),
        sa.CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="ck_call_logs_duration_nonnegative"),
        sa.CheckConstraint("status IN ('queued', 'initiated', 'ringing', 'in_progress', 'completed', 'no_answer', 'busy', 'failed', 'cancelled')", name="ck_call_logs_status"),
        sa.CheckConstraint("outcome IS NULL OR outcome IN ('resolved', 'unresolved', 'transferred', 'unknown')", name="ck_call_logs_outcome"),
    )
    op.create_index("ix_call_logs_customer_phone", "call_logs", ["customer_phone"])
    op.create_index("ix_call_logs_ticket_id", "call_logs", ["ticket_id"])
    op.create_index("ix_call_logs_parent_call_log_id", "call_logs", ["parent_call_log_id"])
    op.create_index("ix_call_logs_ticket_created", "call_logs", ["ticket_id", "created_at"])
    op.create_index("ix_call_logs_status_created", "call_logs", ["status", "created_at"])
    op.create_index("ix_call_logs_customer_created", "call_logs", ["customer_phone", "created_at"])

    op.create_table(
        "kb_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_uri", sa.String(length=512), unique=True),
        sa.Column("storage_uri", sa.String(length=512)),
        sa.Column("source_checksum", sa.String(length=64)),
        sa.Column("mime_type", sa.String(length=127)),
        sa.Column("content", sa.Text()),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("ingestion_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("ingestion_error", sa.Text()),
        sa.Column("embedded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("ingestion_status IN ('pending', 'processing', 'ready', 'failed')", name="ck_kb_documents_ingestion_status"),
    )
    op.create_index("ix_kb_documents_source_checksum", "kb_documents", ["source_checksum"])
    op.create_index("ix_kb_documents_status_created", "kb_documents", ["ingestion_status", "created_at"])

    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("character_start", sa.Integer()),
        sa.Column("character_end", sa.Integer()),
        sa.Column("token_count", sa.Integer()),
        sa.Column("vector_id", sa.String(length=255), unique=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("chunk_index >= 0", name="ck_kb_chunks_index_nonnegative"),
        sa.CheckConstraint("token_count IS NULL OR token_count >= 0", name="ck_kb_chunks_token_count_nonnegative"),
        sa.CheckConstraint("page_number IS NULL OR page_number > 0", name="ck_kb_chunks_page_positive"),
        sa.CheckConstraint("character_end IS NULL OR character_start IS NULL OR character_end >= character_start", name="ck_kb_chunks_character_range"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_kb_chunks_document_index"),
    )
    op.create_index("ix_kb_chunks_document_index", "kb_chunks", ["document_id", "chunk_index"])


def downgrade() -> None:
    op.drop_table("kb_chunks")
    op.drop_table("kb_documents")
    op.drop_table("call_logs")
