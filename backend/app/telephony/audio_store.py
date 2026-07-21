"""Redis storage for deferred telephony speech and synthesized-audio caching.

Module: Telephony & Call Orchestration. Webhooks store short-lived text tokens;
the audio endpoint resolves and synthesizes them when Twilio fetches `<Play>`.
"""
import hashlib
import json
import logging
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

import redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)

# Persistent on-disk cache for pre-generated ("downloaded") static-phrase audio.
# Unlike the Redis cache it has no TTL and survives restarts, so the greeting and
# closing lines never fall back to a live TTS round-trip. Keyed by the same
# _audio_key hash as Redis, under app/data/assets (shared asset location).
_DISK_CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "assets" / "tts"


@lru_cache(maxsize=1)
def _redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=False)


def store_text(text_ar: str) -> str:
    """Store spoken text under a short-lived opaque token."""
    token = uuid4().hex
    _redis().setex(
        f"telephony:say:{token}",
        settings.telephony_audio_ttl_seconds,
        text_ar,
    )
    return token


def fetch_text(token: str) -> str | None:
    """Resolve a speech token, returning None when it is missing or expired."""
    value = _redis().get(f"telephony:say:{token}")
    if value is None:
        return None
    return value.decode("utf-8") if isinstance(value, bytes) else value


def _audio_key(text_ar: str) -> str:
    source = json.dumps(
        [
            settings.elevenlabs_voice_id,
            settings.elevenlabs_output_format,
            settings.elevenlabs_model_id,
            settings.elevenlabs_text_normalization,
            settings.elevenlabs_pronunciation_dictionary_id,
            settings.elevenlabs_pronunciation_dictionary_version_id,
            settings.elevenlabs_stability,
            settings.elevenlabs_similarity_boost,
            settings.elevenlabs_style,
            settings.elevenlabs_use_speaker_boost,
            text_ar,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"telephony:tts:{hashlib.sha256(source.encode('utf-8')).hexdigest()}"


def _disk_path(key: str) -> Path:
    """Map an _audio_key to its on-disk cache file (hash is the filename)."""
    return _DISK_CACHE_DIR / f"{key.rsplit(':', 1)[-1]}.audio"


def get_cached_audio(text_ar: str) -> bytes | None:
    """Return cached synthesized audio, treating any cache failure as a miss.

    Checks Redis first (hot, TTL'd), then the persistent on-disk cache. The disk
    layer holds pre-generated static phrases (prewarm_disk_cache), so the
    greeting and closing lines are served instantly even after the Redis entry
    expires or the process restarts — no live TTS synthesis on playback.
    """
    key = _audio_key(text_ar)
    try:
        cached = _redis().get(key)
        if cached is not None:
            return cached
    except RedisError:
        logger.warning("could not read telephony TTS cache", exc_info=True)

    path = _disk_path(key)
    try:
        if path.is_file():
            return path.read_bytes()
    except OSError:
        logger.warning("could not read pre-generated telephony audio", exc_info=True)
    return None


def cache_audio(text_ar: str, audio: bytes) -> None:
    """Cache completed synthesized audio without making playback depend on Redis."""
    try:
        _redis().setex(_audio_key(text_ar), settings.tts_cache_ttl_seconds, audio)
    except RedisError:
        logger.warning("could not write telephony TTS cache", exc_info=True)


def audio_content_type() -> str:
    """Map the configured ElevenLabs output format to an HTTP media type."""
    output_format = settings.elevenlabs_output_format
    if output_format.startswith("mp3_"):
        return "audio/mpeg"
    if output_format.startswith("ulaw_"):
        return "audio/basic"
    if output_format.startswith("pcm_") or output_format == "wav":
        return "audio/wav"
    return "application/octet-stream"


def play_url(token: str) -> str:
    """Build the public URL Twilio fetches for a speech token."""
    return f"{settings.public_base_url}/telephony/audio/{token}"


def prewarm_disk_cache(phrases: Iterable[str], *, force: bool = False) -> int:
    """Pre-generate ("download") audio for `phrases` into the on-disk cache.

    Synthesizes each phrase once via ElevenLabs and writes it under
    _DISK_CACHE_DIR keyed by _audio_key, so later playback (get_cached_audio)
    never blocks on a live TTS round-trip. Idempotent: an existing file is
    skipped unless `force` is set (use force after changing voice/model/format,
    since those are part of the key and would otherwise leave stale files).
    Returns the number of files written.
    """
    # Local import: keeps the telephony module import-light and avoids a hard
    # dependency on the speech provider just to load audio_store.
    from app.speech import tts

    _DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for text_ar in phrases:
        if not text_ar or not text_ar.strip():
            continue
        path = _disk_path(_audio_key(text_ar))
        if path.is_file() and not force:
            continue
        audio = tts.synthesize(text_ar)
        path.write_bytes(audio)
        written += 1
    return written
