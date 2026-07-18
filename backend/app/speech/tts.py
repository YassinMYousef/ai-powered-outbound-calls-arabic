"""Arabic text-to-speech via ElevenLabs — natural-sounding neural voices.

Module: Speech Processing (Sprint 2). SDK-free: the REST call goes through
httpx (same pattern as rag/embeddings.py) so swapping providers touches only
this file. Everything provider-specific — voice, model, output format,
normalization, pronunciation dictionary, voice tuning — lives in settings.

Two ElevenLabs quality levers are wired in per the call-center requirements:

- Text normalization (settings.elevenlabs_text_normalization) spells out
  numbers, dates and currency, so a ticket ID or an amount interpolated into
  the greeting is spoken naturally instead of digit-by-digit.
- A pronunciation dictionary (settings.elevenlabs_pronunciation_dictionary_*)
  pins how domain terms — product/plan names, proper nouns — are voiced. Both
  the dictionary ID and a version ID are required; when either is blank no
  locator is sent.

Both features need a full model (eleven_multilingual_v2); the low-latency
turbo/flash models only accept normalization="auto".
"""
from collections.abc import Iterator
from functools import lru_cache

import httpx

from app.config import settings


@lru_cache(maxsize=1)
def _client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.elevenlabs_base_url,
        timeout=httpx.Timeout(60.0, connect=10.0),
    )


def _voice_settings() -> dict:
    return {
        "stability": settings.elevenlabs_stability,
        "similarity_boost": settings.elevenlabs_similarity_boost,
        "style": settings.elevenlabs_style,
        "use_speaker_boost": settings.elevenlabs_use_speaker_boost,
    }


def _pronunciation_locators() -> list[dict] | None:
    dictionary_id = settings.elevenlabs_pronunciation_dictionary_id
    version_id = settings.elevenlabs_pronunciation_dictionary_version_id
    if dictionary_id and version_id:
        return [{
            "pronunciation_dictionary_id": dictionary_id,
            "version_id": version_id,
        }]
    return None


def synthesize(text_ar: str, voice: str | None = None) -> bytes:
    """Render Arabic text to audio bytes for telephony playback.

    Used for the dynamic greeting (see speech/greeting.py) and every dialog
    turn. Returns raw audio in settings.elevenlabs_output_format — default is
    natural-quality mp3; set the format to "ulaw_8000" to get Twilio-ready
    audio directly and bypass speech/audio.py.

    `voice` overrides settings.elevenlabs_voice_id for a single call.
    """
    if not text_ar or not text_ar.strip():
        raise ValueError("synthesize() requires non-empty text")
    if not settings.tts_api_key:
        raise RuntimeError("TTS_API_KEY (ElevenLabs) is not set — TTS cannot run")

    voice_id = voice or settings.elevenlabs_voice_id
    body: dict = {
        "text": text_ar,
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": _voice_settings(),
        "apply_text_normalization": settings.elevenlabs_text_normalization,
    }
    locators = _pronunciation_locators()
    if locators:
        body["pronunciation_dictionary_locators"] = locators

    try:
        response = _client().post(
            f"/v1/text-to-speech/{voice_id}",
            params={"output_format": settings.elevenlabs_output_format},
            headers={"xi-api-key": settings.tts_api_key, "accept": "audio/*"},
            json=body,
        )
    except httpx.TransportError as exc:
        raise RuntimeError(
            f"ElevenLabs unreachable at {settings.elevenlabs_base_url}: {exc}"
        ) from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs TTS failed ({response.status_code}): {response.text[:500]}"
        )
    return response.content


def synthesize_stream(text_ar: str, voice: str | None = None) -> Iterator[bytes]:
    """Stream Arabic speech audio using the same contract as `synthesize`."""
    if not text_ar or not text_ar.strip():
        raise ValueError("synthesize_stream() requires non-empty text")
    if not settings.tts_api_key:
        raise RuntimeError("TTS_API_KEY (ElevenLabs) is not set — TTS cannot run")

    voice_id = voice or settings.elevenlabs_voice_id
    body: dict = {
        "text": text_ar,
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": _voice_settings(),
        "apply_text_normalization": settings.elevenlabs_text_normalization,
    }
    locators = _pronunciation_locators()
    if locators:
        body["pronunciation_dictionary_locators"] = locators

    def generate() -> Iterator[bytes]:
        try:
            with _client().stream(
                "POST",
                f"/v1/text-to-speech/{voice_id}/stream",
                params={"output_format": settings.elevenlabs_output_format},
                headers={"xi-api-key": settings.tts_api_key, "accept": "audio/*"},
                json=body,
            ) as response:
                if response.status_code != 200:
                    response.read()
                    raise RuntimeError(
                        f"ElevenLabs TTS failed ({response.status_code}): {response.text[:500]}"
                    )
                yield from response.iter_bytes()
        except httpx.TransportError as exc:
            raise RuntimeError(
                f"ElevenLabs unreachable at {settings.elevenlabs_base_url}: {exc}"
            ) from exc

    return generate()
