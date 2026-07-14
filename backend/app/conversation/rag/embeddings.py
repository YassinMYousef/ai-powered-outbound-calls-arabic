"""Embedding client — local TEI (text-embeddings-inference) server.

Module: Conversation/RAG. Keep all embedding-provider calls behind this
wrapper so the provider stays swappable (settings.tei_url / embedding_model).

The e5 model family requires task prefixes on every input — "passage: " for
documents at ingest time, "query: " for questions at retrieval time. They are
applied here so callers never worry about them; mixing them up silently
degrades retrieval quality.
"""
from functools import lru_cache

import httpx

from app.config import settings

# e5-large on CPU runs ~15-20s per full-size chunk, so a request's cost scales with
# the batch. Keep batches small and the read timeout generous — ingestion is a
# background job; a whole document should never ride on one long-lived request.
_BATCH_SIZE = 4
_READ_TIMEOUT = 300.0


@lru_cache(maxsize=1)
def _client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.tei_url, timeout=httpx.Timeout(_READ_TIMEOUT, connect=10.0)
    )


def _embed(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        try:
            response = _client().post("/embed", json={"inputs": batch})
        except httpx.TimeoutException as exc:
            # Distinct from "unreachable": the server is up but slower than the
            # timeout. Don't send the caller chasing a container that's running.
            raise RuntimeError(
                f"embedding server at {settings.tei_url} timed out after {_READ_TIMEOUT:.0f}s "
                f"on a batch of {len(batch)} — is it running on CPU under heavy load?"
            ) from exc
        except httpx.TransportError as exc:
            raise RuntimeError(
                f"embedding server unreachable at {settings.tei_url} — "
                "start it with `docker compose up -d tei` (first start downloads the model)"
            ) from exc
        response.raise_for_status()
        vectors.extend(response.json())
    return vectors


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed document chunks for storage. Preserves input order."""
    return _embed([f"passage: {t}" for t in texts])


def embed_query(text: str) -> list[float]:
    """Embed a user question for similarity search."""
    return _embed([f"query: {text}"])[0]
