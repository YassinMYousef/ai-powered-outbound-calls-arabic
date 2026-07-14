"""Arabic speech-to-text via the OpenAI Whisper API.

Module: Speech Processing (Sprint 1). One SDK call, isolated behind
transcribe() so the STT provider stays swappable (settings.stt_model).

Egyptian Arabic and Modern Standard Arabic both decode under language="ar";
Whisper has no dialect switch. To bias decoding toward Egyptian colloquial
spelling and in-domain vocabulary, seed settings.stt_prompt_ar with a short
sample of the phrasing you expect (it is a soft hint, not a grammar) — this is
the lever the Sprint 1 accuracy pass tunes against real test-call recordings.
"""
import io
from functools import lru_cache

from openai import OpenAI, OpenAIError

from app.config import settings


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set — STT cannot run")
    return OpenAI(api_key=settings.openai_api_key)


def transcribe(audio_wav: bytes, language: str = "ar") -> str:
    """Transcribe call audio (16 kHz mono WAV) to Arabic text.

    Returns "" for empty input (silence / a failed capture) so callers can feed
    the result straight into dialog.classify_intent, which maps "" to
    Intent.UNKNOWN rather than mis-firing a real intent.
    """
    if not audio_wav:
        return ""

    # The OpenAI SDK infers the upload format from the file's name attribute.
    audio_file = io.BytesIO(audio_wav)
    audio_file.name = "call.wav"

    try:
        result = _client().audio.transcriptions.create(
            model=settings.stt_model,
            file=audio_file,
            language=language,
            prompt=settings.stt_prompt_ar or None,
            response_format="text",
            temperature=0.0,
        )
    except OpenAIError as exc:
        raise RuntimeError(f"STT request failed: {exc}") from exc

    # response_format="text" yields a bare string; guard for SDK objects too.
    text = result if isinstance(result, str) else getattr(result, "text", "")
    return text.strip()
