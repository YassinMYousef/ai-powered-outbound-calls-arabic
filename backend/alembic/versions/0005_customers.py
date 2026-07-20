"""Add the customers table and link follow_up_tickets to it.

follow_up_tickets keeps its denormalized customer_name/customer_phone snapshot
(what the CRM sent); customer_id is the optional link to the local mirror.

Revision ID: 0005_customers
Revises: 0004_rag_query_cache
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_customers"
down_revision: Union[str, None] = "0004_rag_query_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("governorate", sa.String(length=64), nullable=True),
        sa.Column(
            "preferred_language", sa.String(length=8), server_default="ar-EG", nullable=False
        ),
        sa.Column("crm_customer_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "preferred_language IN ('ar-EG', 'ar')", name="ck_customers_preferred_language"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone", name="uq_customers_phone"),
        sa.UniqueConstraint("crm_customer_id", name="uq_customers_crm_customer_id"),
    )

    with op.batch_alter_table("follow_up_tickets") as batch_op:
        batch_op.add_column(sa.Column("customer_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_follow_up_tickets_customer_id",
            "customers",
            ["customer_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_follow_up_tickets_customer_id", "follow_up_tickets", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_follow_up_tickets_customer_id", table_name="follow_up_tickets")
    with op.batch_alter_table("follow_up_tickets") as batch_op:
        batch_op.drop_constraint("fk_follow_up_tickets_customer_id", type_="foreignkey")
        batch_op.drop_column("customer_id")
    op.drop_table("customers")
