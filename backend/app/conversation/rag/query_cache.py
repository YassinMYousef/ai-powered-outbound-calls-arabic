"""Two-level query cache for RAG answers: L0 exact (Redis) + L1 semantic (pgvector).

Module: Conversation/RAG. A hit returns the exact {"answer", "sources"} dict
answer.py produced for an equivalent earlier question, skipping retrieval and
generation. L0 collapses orthographic variants of the same Arabic question via
lexical.tokenize; L1 matches paraphrases by cosine similarity over the cached
query embeddings (rag_query_cache table).

Failure policy mirrors telephony/audio_store.py: every Redis/DB failure is a
logged warning and behaves as a miss (reads) or a no-op (writes) — the cache
must never take down a chat turn. Entries expire after
settings.rag_query_cache_ttl_seconds (L0 via SETEX, L1 via a created_at cutoff
enforced on read and pruned on write) and both levels are flushed by
invalidate_all() whenever the KB changes.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import redis
from redis.exceptions import RedisError
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.conversation.rag import lexical

logger = logging.getLogger(__name__)

# Bumped (INCR) on KB change: old L0 keys become unreachable in O(1) — no SCAN —
# and Redis evicts them when their TTL lapses.
_VERSION_KEY = "rag:qcache:version"


@lru_cache(maxsize=1)
def _redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=False)


def _l0_key(query_ar: str, top_k: int) -> str:
    # lexical.tokenize is the retrieval arms' Arabic normalization (tashkeel and
    # tatweel stripped, alef/yaa/taa-marbuta unified, lowercased) — surface
    # variants of the same question collapse to one key.
    normalized = " ".join(lexical.tokenize(query_ar))
    version = (_redis().get(_VERSION_KEY) or b"0").decode()
    source = json.dumps(
        [normalized, top_k, settings.answer_model],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return f"rag:qcache:{version}:{digest}"


def _ttl_cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=settings.rag_query_cache_ttl_seconds)


def get_exact(query_ar: str, top_k: int) -> dict | None:
    """L0: exact-match lookup on the normalized query. ~1ms Redis GET."""
    try:
        value = _redis().get(_l0_key(query_ar, top_k))
    except RedisError:
        logger.warning("could not read L0 query cache; treating as miss", exc_info=True)
        return None
    return json.loads(value) if value else None


def _nearest(
    db: Session, vector: list[float], top_k: int, model: str, cutoff: datetime
) -> tuple[dict, float] | None:
    """(payload, cosine similarity) of the closest fresh entry, or None.

    Postgres-only, like vectorstore.query_chunks — tests fake this seam.
    """
    from app.data.models import RagQueryCache

    distance = RagQueryCache.embedding.cosine_distance(vector)
    row = db.execute(
        select(RagQueryCache.payload, distance.label("distance"))
        .where(
            RagQueryCache.top_k == top_k,
            RagQueryCache.model == model,
            RagQueryCache.created_at >= cutoff,
        )
        .order_by(distance)
        .limit(1)
    ).first()
    if row is None:
        return None
    return row.payload, 1.0 - row.distance


def get_semantic(vector: list[float], top_k: int) -> dict | None:
    """L1: nearest cached query by cosine similarity, gated by the threshold.

    Opens its own session — answer.py runs this concurrently with retrieval
    (which also opens its own), and sessions must not cross threads.
    """
    from app.data.db import SessionLocal

    try:
        with SessionLocal() as db:
            hit = _nearest(db, vector, top_k, settings.answer_model, _ttl_cutoff())
    except SQLAlchemyError:
        logger.warning("could not read L1 query cache; treating as miss", exc_info=True)
        return None
    if hit is None:
        return None
    payload, similarity = hit
    if similarity < settings.rag_query_cache_similarity_threshold:
        return None
    return payload


def put(query_ar: str, vector: list[float], top_k: int, result: dict) -> None:
    """Populate both levels after a generated answer. Never raises."""
    try:
        _redis().setex(
            _l0_key(query_ar, top_k),
            settings.rag_query_cache_ttl_seconds,
            json.dumps(result, ensure_ascii=False),
        )
    except RedisError:
        logger.warning("could not write L0 query cache", exc_info=True)

    from app.data.db import SessionLocal
    from app.data.models import RagQueryCache

    try:
        with SessionLocal() as db:
            # Delete-on-write is the whole L1 expiry story — no scheduled task;
            # the created_at cutoff in _nearest keeps reads correct meanwhile.
            db.execute(delete(RagQueryCache).where(RagQueryCache.created_at < _ttl_cutoff()))
            db.add(
                RagQueryCache(
                    query=query_ar,
                    embedding=vector,
                    top_k=top_k,
                    model=settings.answer_model,
                    payload=result,
                )
            )
            db.commit()
    except SQLAlchemyError:
        logger.warning("could not write L1 query cache", exc_info=True)


def invalidate_all() -> None:
    """KB changed: every cached answer may cite the pre-change KB — flush both levels.

    No-op while the cache is disabled (nothing is being read or written, and
    ingestion must not grow a Redis/Postgres dependency it doesn't need); any
    entry that survives a disable/re-enable window still expires via the TTL.
    """
    if not settings.rag_query_cache_enabled:
        return
    try:
        _redis().incr(_VERSION_KEY)
    except RedisError:
        logger.warning("could not invalidate L0 query cache", exc_info=True)

    from app.data.db import SessionLocal
    from app.data.models import RagQueryCache

    try:
        with SessionLocal() as db:
            db.execute(delete(RagQueryCache))
            db.commit()
    except SQLAlchemyError:
        logger.warning("could not invalidate L1 query cache", exc_info=True)
