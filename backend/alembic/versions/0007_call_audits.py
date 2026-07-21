"""Add call_audits — the report-accuracy audit trail.

One row per manual QA verdict on a completed call (see data/models.CallAudit and
data/reporting.report_accuracy). All standard column types, so it runs unchanged
on Postgres and SQLite (tests); now() defaults are CURRENT_TIMESTAMP for the same
reason. Foreign keys use CASCADE (audit dies with its call) / SET NULL (keep the
audit if the auditor's user record is removed).

Revision ID: 0007_call_audits
Revises: 0006_unanswered_questions
Create Date: 2026-07-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_call_audits"
down_revision: Union[str, None] = "0006_unanswered_questions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    op.create_table(
        "call_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("call_log_id", sa.Integer(), nullable=False),
        sa.Column("ai_outcome", sa.String(length=32), nullable=True),
        sa.Column("audited_outcome", sa.String(length=32), nullable=False),
        sa.Column("is_accurate", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("audited_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "audited_outcome IN ('resolved', 'unresolved', 'transferred', 'unknown')",
            name="ck_call_audits_audited_outcome",
        ),
        sa.ForeignKeyConstraint(["call_log_id"], ["call_logs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audited_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_log_id", name="uq_call_audits_call_log"),
    )
    op.create_index("ix_call_audits_call_log_id", "call_audits", ["call_log_id"])
    op.create_index("ix_call_audits_created", "call_audits", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_call_audits_created", table_name="call_audits")
    op.drop_index("ix_call_audits_call_log_id", table_name="call_audits")
    op.drop_table("call_audits")
