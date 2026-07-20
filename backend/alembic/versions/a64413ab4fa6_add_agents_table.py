"""add agents table

A roster a manager maintains — not an auth account (data/auth.py's
OAuth2/RBAC is still unimplemented) and not yet linked to call_logs.

Revision ID: a64413ab4fa6
Revises: 6d3bc12f912a
Create Date: 2026-07-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a64413ab4fa6"
down_revision: Union[str, None] = "6d3bc12f912a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_agents_email"),
    )
    op.create_index("ix_agents_email", "agents", ["email"])


def downgrade() -> None:
    op.drop_index("ix_agents_email", table_name="agents")
    op.drop_table("agents")
