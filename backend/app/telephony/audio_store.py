"""Redis storage for deferred telephony speech and synthesized-audio caching.

Module: Telephony & Call Orchestration. Webhooks store short-lived text tokens;
the audio endpoint resolves and synthesizes them when Twilio fetches `<Play>`.
"""
import hashlib
import json
import logging
from functools import lru_cache
from uuid import uuid4

import redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)


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


def get_cached_audio(text_ar: str) -> bytes | None:
    """Return cached synthesized audio, treating Redis failures as misses."""
    try:
        return _redis().get(_audio_key(text_ar))
    except RedisError:
        logger.warning("could not read telephony TTS cache", exc_info=True)
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
