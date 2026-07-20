"""Add unanswered_questions — the KB-gap log.

One row per chat turn the KB could not answer (see data/models.UnansweredQuestion
and data/kb_gaps.py). All standard column types, so the migration runs unchanged
on Postgres and SQLite (tests); now() defaults are CURRENT_TIMESTAMP for the same
reason. Foreign keys use SET NULL so deleting a chat session or user never erases
the gap history admins review.

Chained after 0005_customers (both 0005_customers and this branched from 0004
during parallel development; linearized here to keep a single Alembic head).

Revision ID: 0006_unanswered_questions
Revises: 0005_customers
Create Date: 2026-07-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_unanswered_questions"
down_revision: Union[str, None] = "0005_customers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    op.create_table(
        "unanswered_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("chunks_retrieved", sa.Integer(), nullable=True),
        sa.Column("top_similarity", sa.Float(), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "reason IN ('no_match', 'no_citation', 'low_confidence')",
            name="ck_unanswered_questions_reason",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')",
            name="ck_unanswered_questions_status",
        ),
        sa.CheckConstraint(
            "chunks_retrieved IS NULL OR chunks_retrieved >= 0",
            name="ck_unanswered_questions_chunks_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_unanswered_questions_session_id", "unanswered_questions", ["session_id"]
    )
    op.create_index(
        "ix_unanswered_questions_status_created",
        "unanswered_questions",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_unanswered_questions_normalized", "unanswered_questions", ["normalized_query"]
    )


def downgrade() -> None:
    op.drop_index("ix_unanswered_questions_normalized", table_name="unanswered_questions")
    op.drop_index("ix_unanswered_questions_status_created", table_name="unanswered_questions")
    op.drop_index("ix_unanswered_questions_session_id", table_name="unanswered_questions")
    op.drop_table("unanswered_questions")
