"""Extend the customers table with CRM-mirror columns, and link follow_up_tickets.

6d3bc12f912a (Person B, Sprint 4) created `customers` as name/phone/notes. When
that branch merged with this one, the two `customers` designs were unified into
one superset table: this migration adds the richer CRM-mirror columns (email,
governorate, preferred_language, crm_customer_id) the follow-up scheduler and
TTS register use, then links follow_up_tickets to it. follow_up_tickets keeps
its denormalized customer_name/customer_phone snapshot (what the CRM sent);
customer_id is the optional link to the local mirror.

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


def upgrade() -> None:
    # batch mode so SQLite (tests) recreates the table to add columns/constraints;
    # preferred_language is NOT NULL with a server_default so existing rows fill in.
    with op.batch_alter_table("customers") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("governorate", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "preferred_language",
                sa.String(length=8),
                server_default="ar-EG",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("crm_customer_id", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint("uq_customers_crm_customer_id", ["crm_customer_id"])
        batch_op.create_check_constraint(
            "ck_customers_preferred_language", "preferred_language IN ('ar-EG', 'ar')"
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

    with op.batch_alter_table("customers") as batch_op:
        batch_op.drop_constraint("ck_customers_preferred_language", type_="check")
        batch_op.drop_constraint("uq_customers_crm_customer_id", type_="unique")
        batch_op.drop_column("crm_customer_id")
        batch_op.drop_column("preferred_language")
        batch_op.drop_column("governorate")
        batch_op.drop_column("email")
