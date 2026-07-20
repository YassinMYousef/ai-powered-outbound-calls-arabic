from datetime import datetime, timedelta, timezone

import pytest
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.conversation.rag import lexical, query_cache
from app.data.models import RagQueryCache

RESULT = {
    "answer": "ادخل إلى النظام الداخلي واضغط تعديل.",
    "sources": [{"doc_id": 7, "title": "دليل العمليات", "quotes": ["اضغط تعديل"]}],
}
VECTOR = [0.1, 0.2]


class FakeRedis:
    """The four Redis calls query_cache makes, over a dict. Set `broken` to
    simulate an outage — every call then raises RedisError."""

    def __init__(self):
        self.store: dict[str, bytes] = {}
        self.broken = False

    def _check(self):
        if self.broken:
            raise RedisError("redis down")

    def get(self, key):
        self._check()
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self._check()
        self.store[key] = value.encode() if isinstance(value, str) else value

    def incr(self, key):
        self._check()
        self.store[key] = str(int(self.store.get(key, b"0")) + 1).encode()


@pytest.fixture
def fake_redis(monkeypatch, db_session):
    """Enable the cache with Redis faked and SessionLocal bound to the test DB."""
    fake = FakeRedis()
    monkeypatch.setattr(query_cache, "_redis", lambda: fake)
    monkeypatch.setattr(settings, "rag_query_cache_enabled", True)
    factory = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    monkeypatch.setattr("app.data.db.SessionLocal", factory)
    return fake


# --- L0: exact match --------------------------------------------------------


def test_l0_put_then_get_hits(fake_redis, db_session) -> None:
    assert query_cache.get_exact("كيف أحدث بيانات العميل؟", 5) is None
    query_cache.put("كيف أحدث بيانات العميل؟", VECTOR, 5, RESULT)
    assert query_cache.get_exact("كيف أحدث بيانات العميل؟", 5) == RESULT


def test_l0_collapses_arabic_surface_variants(fake_redis, db_session) -> None:
    # Same question with tashkeel, hamza-on-alef, and punctuation differences —
    # lexical.tokenize normalization must map all of them to one key.
    query_cache.put("كيف احدث بيانات العميل", VECTOR, 5, RESULT)
    assert query_cache.get_exact("كَيف أحدث بياناتِ العميل؟", 5) == RESULT


def test_l0_key_discriminates_top_k_and_model(fake_redis, db_session, monkeypatch) -> None:
    query_cache.put("سؤال", VECTOR, 5, RESULT)
    assert query_cache.get_exact("سؤال", 3) is None  # different top_k
    monkeypatch.setattr(settings, "answer_model", "some-other-model")
    assert query_cache.get_exact("سؤال", 5) is None  # different answer model


def test_l0_redis_outage_is_a_miss_not_an_error(fake_redis, db_session) -> None:
    fake_redis.broken = True
    assert query_cache.get_exact("سؤال", 5) is None
    query_cache.put("سؤال", VECTOR, 5, RESULT)  # must not raise
    fake_redis.broken = False
    assert query_cache.get_exact("سؤال", 5) is None  # L0 write was skipped


# --- L1: semantic -----------------------------------------------------------


def test_l1_hit_requires_similarity_at_or_above_threshold(fake_redis, monkeypatch) -> None:
    for similarity, expected in [(0.96, RESULT), (0.95, RESULT), (0.94, None)]:
        monkeypatch.setattr(query_cache, "_nearest", lambda *a, sim=similarity: (RESULT, sim))
        assert query_cache.get_semantic(VECTOR, 5) == expected
    monkeypatch.setattr(query_cache, "_nearest", lambda *a: None)
    assert query_cache.get_semantic(VECTOR, 5) is None


def test_l1_lookup_scopes_to_top_k_model_and_ttl_cutoff(fake_redis, monkeypatch) -> None:
    seen: dict = {}

    def fake_nearest(db, vector, top_k, model, cutoff):
        seen.update(vector=vector, top_k=top_k, model=model, cutoff=cutoff)
        return None

    monkeypatch.setattr(query_cache, "_nearest", fake_nearest)
    query_cache.get_semantic(VECTOR, 5)

    assert seen["vector"] == VECTOR
    assert seen["top_k"] == 5
    assert seen["model"] == settings.answer_model
    expected = datetime.now(timezone.utc) - timedelta(
        seconds=settings.rag_query_cache_ttl_seconds
    )
    assert abs((seen["cutoff"] - expected).total_seconds()) < 5


def test_put_stores_l1_row_and_prunes_expired_ones(fake_redis, db_session) -> None:
    expired = RagQueryCache(
        query="سؤال قديم",
        embedding=VECTOR,
        top_k=5,
        model=settings.answer_model,
        payload=RESULT,
        created_at=datetime.now(timezone.utc)
        - timedelta(seconds=settings.rag_query_cache_ttl_seconds + 3600),
    )
    db_session.add(expired)
    db_session.commit()

    query_cache.put("سؤال جديد", VECTOR, 5, RESULT)

    # put wrote via its own session; SQLite reuses the pruned row's id, so the
    # identity map must be dropped or it would echo the stale 'expired' object.
    db_session.expire_all()
    rows = db_session.execute(select(RagQueryCache)).scalars().all()
    assert [row.query for row in rows] == ["سؤال جديد"]
    assert rows[0].embedding == VECTOR
    assert rows[0].payload == RESULT
    assert rows[0].model == settings.answer_model


# --- invalidation -----------------------------------------------------------


def test_invalidate_all_flushes_both_levels(fake_redis, db_session) -> None:
    query_cache.put("سؤال", VECTOR, 5, RESULT)
    assert query_cache.get_exact("سؤال", 5) == RESULT

    query_cache.invalidate_all()

    assert query_cache.get_exact("سؤال", 5) is None  # version bump orphaned the key
    assert db_session.execute(select(RagQueryCache)).scalars().all() == []


def test_invalidate_all_is_a_noop_while_disabled(fake_redis, monkeypatch) -> None:
    monkeypatch.setattr(settings, "rag_query_cache_enabled", False)
    fake_redis.broken = True  # would raise on any Redis touch
    query_cache.invalidate_all()


# --- key derivation uses the shared normalizer ------------------------------


def test_query_cache_module_uses_shared_lexical_wrapper() -> None:
    assert query_cache.lexical is lexical
