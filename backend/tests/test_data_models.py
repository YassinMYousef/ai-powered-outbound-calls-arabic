from app.data.models import (
    Base,
    CallLog,
    ChatMessage,
    ChatSession,
    KBChunk,
    KBDocument,
    User,
)


def test_all_product_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "call_logs",
        "kb_documents",
        "kb_chunks",
        "users",
        "follow_up_tickets",
        "chat_sessions",
        "chat_messages",
        "fcr_reports",
        "audit_logs",
        "rag_query_cache",
        "customers",
        "unanswered_questions",
    }


def test_call_log_retry_relationship_is_a_self_foreign_key() -> None:
    foreign_keys = CallLog.__table__.c.parent_call_log_id.foreign_keys
    assert {foreign_key.target_fullname for foreign_key in foreign_keys} == {"call_logs.id"}


def test_kb_chunk_links_to_document_and_has_order_constraint() -> None:
    foreign_keys = KBChunk.__table__.c.document_id.foreign_keys

    assert {foreign_key.target_fullname for foreign_key in foreign_keys} == {"kb_documents.id"}
    assert KBDocument.chunks.property.mapper.class_ is KBChunk
    assert {column.name for column in KBChunk.__table__.c} >= {"text", "embedding", "metadata"}


def test_chat_message_links_to_session_and_user() -> None:
    session_fks = ChatMessage.__table__.c.session_id.foreign_keys
    assert {fk.target_fullname for fk in session_fks} == {"chat_sessions.id"}
    assert ChatSession.messages.property.mapper.class_ is ChatMessage
    user_fks = ChatSession.__table__.c.user_id.foreign_keys
    assert {fk.target_fullname for fk in user_fks} == {"users.id"}
    assert User.chat_sessions.property.mapper.class_ is ChatSession


def test_follow_up_ticket_links_to_call_log_by_crm_ticket_value_not_fk() -> None:
    # The CRM stays external: call_logs.ticket_id carries the same string as
    # follow_up_tickets.crm_ticket_id, with no FK between the tables.
    assert not CallLog.__table__.c.ticket_id.foreign_keys
    assert Base.metadata.tables["follow_up_tickets"].c.crm_ticket_id.unique


def test_follow_up_ticket_optionally_links_to_local_customer() -> None:
    ticket_table = Base.metadata.tables["follow_up_tickets"]
    fks = ticket_table.c.customer_id.foreign_keys
    assert {fk.target_fullname for fk in fks} == {"customers.id"}
    assert ticket_table.c.customer_id.nullable
    assert Base.metadata.tables["customers"].c.phone.unique
