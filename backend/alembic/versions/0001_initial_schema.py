"""initial schema: call_logs, kb_documents, kb_chunks

Hand-written (no live DB existed to autogenerate against). Must stay runnable
on both Postgres (production, pgvector) and SQLite (tests) — Postgres-only
statements are guarded on the dialect.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1024  # matches app.data.models.EMBEDDING_DIM


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgres():
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        embedding_type: sa.types.TypeEngine = Vector(EMBEDDING_DIM)
    else:
        embedding_type = sa.JSON()

    op.create_table(
        "call_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_phone", sa.String(20), nullable=False),
        sa.Column("ticket_id", sa.String(64)),
        sa.Column("provider_call_sid", sa.String(64)),
        sa.Column("outcome", sa.String(32)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("transcript", sa.Text()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "kb_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_uri", sa.String(512)),
        sa.Column("content", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("embedded_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("kb_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    if _is_postgres():
        op.create_index(
            "ix_kb_chunks_embedding_hnsw",
            "kb_chunks",
            ["embedding"],
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        )


def downgrade() -> None:
    op.drop_table("kb_chunks")
    op.drop_table("kb_documents")
    op.drop_table("call_logs")
