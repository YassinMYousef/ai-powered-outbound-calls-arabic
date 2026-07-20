from app.data.models import Base, CallLog, Customer, KBDocument, KBChunk


def test_sprint_one_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {"call_logs", "kb_documents", "kb_chunks", "customers", "agents"}


def test_call_log_links_to_customer() -> None:
    foreign_keys = CallLog.__table__.c.customer_id.foreign_keys
    assert {foreign_key.target_fullname for foreign_key in foreign_keys} == {"customers.id"}
    assert Customer.call_logs.property.mapper.class_ is CallLog


def test_call_log_retry_relationship_is_a_self_foreign_key() -> None:
    foreign_keys = CallLog.__table__.c.parent_call_log_id.foreign_keys
    assert {foreign_key.target_fullname for foreign_key in foreign_keys} == {"call_logs.id"}


def test_kb_chunk_links_to_document_and_has_order_constraint() -> None:
    foreign_keys = KBChunk.__table__.c.document_id.foreign_keys

    assert {foreign_key.target_fullname for foreign_key in foreign_keys} == {"kb_documents.id"}
    assert KBDocument.chunks.property.mapper.class_ is KBChunk
    assert {column.name for column in KBChunk.__table__.c} >= {"text", "embedding", "metadata"}
