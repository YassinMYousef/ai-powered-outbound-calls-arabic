"""The 0001 migration is hand-written (no live DB to autogenerate against) —
prove it actually runs and produces the schema, using SQLite."""
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _upgraded_engine(tmp_path, target: str = "head") -> sa.Engine:
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, target)
    return sa.create_engine(url)


def test_initial_migration_creates_full_schema(tmp_path) -> None:
    inspector = sa.inspect(_upgraded_engine(tmp_path))

    assert {"call_logs", "kb_documents", "kb_chunks"} <= set(inspector.get_table_names())
    kb_document_columns = {c["name"] for c in inspector.get_columns("kb_documents")}
    assert {
        "content_hash",
        "embedded_at",
        "content",
        "storage_uri",
        "metadata",
        "ingestion_status",
    } <= kb_document_columns
    kb_chunk_columns = {c["name"] for c in inspector.get_columns("kb_chunks")}
    assert {"document_id", "chunk_index", "text", "embedding", "metadata"} <= kb_chunk_columns


def test_migrated_schema_matches_models(tmp_path) -> None:
    # A drift here means models.py changed without a migration (repo rule:
    # schema change and migration ship in the same PR).
    from app.data.models import Base

    inspector = sa.inspect(_upgraded_engine(tmp_path))
    for table_name, table in Base.metadata.tables.items():
        migrated = {c["name"] for c in inspector.get_columns(table_name)}
        assert migrated == {c.name for c in table.columns}, table_name
