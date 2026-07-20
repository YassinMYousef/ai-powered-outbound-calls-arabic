"""add customers table and call_logs.customer_id

Person B Sprint 4: the "CRM / Inbound Call Records" system named in the
requirements doc has no real external counterpart in this project, so
`customers` is that source of truth. `call_logs.customer_id` is nullable —
rows dialed ad hoc (e.g. PlaceRealCallForm) without going through a customer
record have none.

Revision ID: 6d3bc12f912a
Revises: 0002_sprint1_data_enhancements
Create Date: 2026-07-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "6d3bc12f912a"
down_revision: Union[str, None] = "0002_sprint1_data_enhancements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone", name="uq_customers_phone"),
    )
    op.create_index("ix_customers_phone", "customers", ["phone"])

    # batch mode (not plain op.add_column + op.create_foreign_key) because SQLite
    # can't ALTER a foreign key onto an existing table outside of table-recreate mode.
    with op.batch_alter_table("call_logs") as batch_op:
        batch_op.add_column(sa.Column("customer_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_call_logs_customer_id", "customers", ["customer_id"], ["id"], ondelete="SET NULL"
        )
    op.create_index("ix_call_logs_customer_id", "call_logs", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_call_logs_customer_id", table_name="call_logs")
    with op.batch_alter_table("call_logs") as batch_op:
        batch_op.drop_constraint("fk_call_logs_customer_id", type_="foreignkey")
        batch_op.drop_column("customer_id")
    op.drop_index("ix_customers_phone", table_name="customers")
    op.drop_table("customers")
