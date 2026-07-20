"""Add rag_query_cache — the L1 semantic level of the chat query cache.

Stores one row per generated answer, keyed by the retrieval query's embedding;
lookups are a cosine LIMIT 1 on Postgres. Like kb_chunks, the vector column is
dialect-guarded so the migration also runs on SQLite (tests); no HNSW index —
the table is small and TTL-bounded, a sequential scan is fine.

Revision ID: 0004_rag_query_cache
Revises: 0003_full_product_schema
Create Date: 2026-07-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0004_rag_query_cache"
down_revision: Union[str, None] = "0003_full_product_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text("CURRENT_TIMESTAMP")
EMBEDDING_DIM = 1024


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        embedding_type: sa.types.TypeEngine = Vector(EMBEDDING_DIM)
    else:
        embedding_type = sa.JSON()
    op.create_table(
        "rag_query_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint("top_k > 0", name="ck_rag_query_cache_top_k_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_query_cache_created_at", "rag_query_cache", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_rag_query_cache_created_at", table_name="rag_query_cache")
    op.drop_table("rag_query_cache")
