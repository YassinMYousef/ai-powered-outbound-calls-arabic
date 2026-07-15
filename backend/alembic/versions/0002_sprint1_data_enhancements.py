"""Add Person D Sprint 1 production fields to main's initial storage schema.

Revision ID: 0002_sprint1_data_enhancements
Revises: 0001
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_sprint1_data_enhancements"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("call_logs") as batch_op:
        batch_op.add_column(sa.Column("parent_call_log_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued")
        )
        batch_op.add_column(sa.Column("failure_reason", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.create_foreign_key(
            "fk_call_logs_parent_call_log_id", "call_logs", ["parent_call_log_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_unique_constraint("uq_call_logs_provider_call_sid", ["provider_call_sid"])
        batch_op.create_check_constraint("ck_call_logs_attempt_number_positive", "attempt_number > 0")
        batch_op.create_check_constraint(
            "ck_call_logs_duration_nonnegative", "duration_seconds IS NULL OR duration_seconds >= 0"
        )
        batch_op.create_check_constraint(
            "ck_call_logs_status",
            "status IN ('queued', 'initiated', 'ringing', 'in_progress', 'completed', "
            "'no_answer', 'busy', 'failed', 'cancelled')",
        )
        batch_op.create_check_constraint(
            "ck_call_logs_outcome",
            "outcome IS NULL OR outcome IN ('resolved', 'unresolved', 'transferred', 'unknown')",
        )
    op.create_index("ix_call_logs_ticket_created", "call_logs", ["ticket_id", "created_at"])
    op.create_index("ix_call_logs_status_created", "call_logs", ["status", "created_at"])
    op.create_index("ix_call_logs_customer_created", "call_logs", ["customer_phone", "created_at"])
    op.create_index("ix_call_logs_customer_phone", "call_logs", ["customer_phone"])
    op.create_index("ix_call_logs_ticket_id", "call_logs", ["ticket_id"])
    op.create_index("ix_call_logs_parent_call_log_id", "call_logs", ["parent_call_log_id"])

    with op.batch_alter_table("kb_documents") as batch_op:
        batch_op.add_column(sa.Column("storage_uri", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("source_checksum", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("mime_type", sa.String(length=127), nullable=True))
        batch_op.add_column(
            sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch_op.add_column(
            sa.Column("ingestion_status", sa.String(length=16), nullable=False, server_default="pending")
        )
        batch_op.add_column(sa.Column("ingestion_error", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.create_check_constraint(
            "ck_kb_documents_ingestion_status",
            "ingestion_status IN ('pending', 'processing', 'ready', 'failed')",
        )
    op.create_index("ix_kb_documents_source_checksum", "kb_documents", ["source_checksum"])
    op.create_index("ix_kb_documents_status_created", "kb_documents", ["ingestion_status", "created_at"])

    with op.batch_alter_table("kb_chunks") as batch_op:
        batch_op.add_column(sa.Column("page_number", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("character_start", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("character_end", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("token_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("vector_id", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.create_unique_constraint("uq_kb_chunks_vector_id", ["vector_id"])
        batch_op.create_check_constraint(
            "ck_kb_chunks_page_positive", "page_number IS NULL OR page_number > 0"
        )
        batch_op.create_check_constraint(
            "ck_kb_chunks_token_count_nonnegative", "token_count IS NULL OR token_count >= 0"
        )
        batch_op.create_check_constraint(
            "ck_kb_chunks_character_range",
            "character_end IS NULL OR character_start IS NULL OR character_end >= character_start",
        )


def downgrade() -> None:
    op.drop_index("ix_kb_documents_status_created", table_name="kb_documents")
    op.drop_index("ix_kb_documents_source_checksum", table_name="kb_documents")
    with op.batch_alter_table("kb_chunks") as batch_op:
        batch_op.drop_constraint("ck_kb_chunks_character_range", type_="check")
        batch_op.drop_constraint("ck_kb_chunks_token_count_nonnegative", type_="check")
        batch_op.drop_constraint("ck_kb_chunks_page_positive", type_="check")
        batch_op.drop_constraint("uq_kb_chunks_vector_id", type_="unique")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("metadata")
        batch_op.drop_column("vector_id")
        batch_op.drop_column("token_count")
        batch_op.drop_column("character_end")
        batch_op.drop_column("character_start")
        batch_op.drop_column("page_number")
    with op.batch_alter_table("kb_documents") as batch_op:
        batch_op.drop_constraint("ck_kb_documents_ingestion_status", type_="check")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("ingestion_error")
        batch_op.drop_column("ingestion_status")
        batch_op.drop_column("metadata")
        batch_op.drop_column("mime_type")
        batch_op.drop_column("source_checksum")
        batch_op.drop_column("storage_uri")
    op.drop_index("ix_call_logs_parent_call_log_id", table_name="call_logs")
    op.drop_index("ix_call_logs_ticket_id", table_name="call_logs")
    op.drop_index("ix_call_logs_customer_phone", table_name="call_logs")
    op.drop_index("ix_call_logs_customer_created", table_name="call_logs")
    op.drop_index("ix_call_logs_status_created", table_name="call_logs")
    op.drop_index("ix_call_logs_ticket_created", table_name="call_logs")
    with op.batch_alter_table("call_logs") as batch_op:
        batch_op.drop_constraint("ck_call_logs_outcome", type_="check")
        batch_op.drop_constraint("ck_call_logs_status", type_="check")
        batch_op.drop_constraint("ck_call_logs_duration_nonnegative", type_="check")
        batch_op.drop_constraint("ck_call_logs_attempt_number_positive", type_="check")
        batch_op.drop_constraint("uq_call_logs_provider_call_sid", type_="unique")
        batch_op.drop_constraint("fk_call_logs_parent_call_log_id", type_="foreignkey")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("attempt_number")
        batch_op.drop_column("failure_reason")
        batch_op.drop_column("status")
        batch_op.drop_column("parent_call_log_id")
