from datetime import datetime, timezone

from app.conversation import memory
from app.data.models import ChatMessage, ChatSession

ANSWER = {
    "answer": "ادخل إلى النظام الداخلي واضغط تعديل.",
    "sources": [{"doc_id": 7, "title": "دليل العمليات", "quotes": ["اضغط تعديل"]}],
}


def test_create_session_flushes_id_without_user(db_session) -> None:
    session = memory.create_session(db_session)
    assert isinstance(session.id, int)
    assert session.user_id is None


def test_get_session_unknown_id_is_none(db_session) -> None:
    assert memory.get_session(db_session, 12345) is None


def test_get_session_returns_live_session(db_session) -> None:
    session = memory.create_session(db_session)
    db_session.commit()
    assert memory.get_session(db_session, session.id) is session


def test_get_session_ended_is_none(db_session) -> None:
    session = memory.create_session(db_session)
    session.ended_at = datetime.now(timezone.utc)
    db_session.commit()
    assert memory.get_session(db_session, session.id) is None


def test_load_history_empty_for_fresh_session(db_session) -> None:
    session = memory.create_session(db_session)
    db_session.commit()
    assert memory.load_history(db_session, session.id, limit=10) == []


def test_append_turn_persists_both_rows_and_touches_session(db_session) -> None:
    session = memory.create_session(db_session)
    before = session.updated_at

    memory.append_turn(db_session, session, "كيف أحدث بيانات العميل؟", ANSWER, latency_ms=850)

    rows = db_session.query(ChatMessage).order_by(ChatMessage.id).all()
    assert [(r.role, r.content) for r in rows] == [
        ("user", "كيف أحدث بيانات العميل؟"),
        ("assistant", ANSWER["answer"]),
    ]
    assert rows[0].sources == []  # user turns carry no citations
    assert rows[1].sources == ANSWER["sources"]
    assert rows[1].latency_ms == 850
    assert session.updated_at != before
    # committed — visible to a rolled-back session
    db_session.rollback()
    assert db_session.query(ChatMessage).count() == 2


def test_load_history_returns_turns_oldest_first(db_session) -> None:
    session = memory.create_session(db_session)
    memory.append_turn(db_session, session, "سؤال أول", ANSWER, latency_ms=1)
    memory.append_turn(db_session, session, "سؤال ثانٍ", ANSWER, latency_ms=1)

    history = memory.load_history(db_session, session.id, limit=10)

    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert history[0] == {"role": "user", "content": "سؤال أول"}
    assert history[2] == {"role": "user", "content": "سؤال ثانٍ"}


def test_load_history_window_keeps_most_recent_messages(db_session) -> None:
    session = memory.create_session(db_session)
    for i in range(4):
        memory.append_turn(db_session, session, f"سؤال {i}", ANSWER, latency_ms=1)

    history = memory.load_history(db_session, session.id, limit=4)

    assert len(history) == 4
    assert history[0] == {"role": "user", "content": "سؤال 2"}
    assert history[2] == {"role": "user", "content": "سؤال 3"}


def test_load_history_never_starts_with_an_assistant_turn(db_session) -> None:
    # An odd limit slices mid-pair; the Messages API requires the first message
    # to be role "user", so the orphaned assistant turn must be trimmed.
    session = memory.create_session(db_session)
    memory.append_turn(db_session, session, "سؤال أول", ANSWER, latency_ms=1)
    memory.append_turn(db_session, session, "سؤال ثانٍ", ANSWER, latency_ms=1)

    history = memory.load_history(db_session, session.id, limit=3)

    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "سؤال ثانٍ"}


def test_history_is_scoped_to_its_session(db_session) -> None:
    first = memory.create_session(db_session)
    second = memory.create_session(db_session)
    memory.append_turn(db_session, first, "سؤال للجلسة الأولى", ANSWER, latency_ms=1)

    assert memory.load_history(db_session, second.id, limit=10) == []
    assert db_session.query(ChatSession).count() == 2
