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
import logging
from functools import lru_cache

from openai import OpenAI, OpenAIError

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set — STT cannot run")
    return OpenAI(api_key=settings.openai_api_key)


def _drop_hallucinated_segments(result) -> str:
    """Keep only segments Whisper itself believes contain speech.

    Whisper hallucinates fluent Arabic over silence and line noise; on a call
    that garbage can match a real intent (e.g. a stray "اه" marking the call
    resolved). Segment-level no_speech_prob / avg_logprob are the model's own
    confidence signals, so gating on them turns noise into "" (→ Intent.UNKNOWN)
    instead of a fabricated reply.
    """
    segments = getattr(result, "segments", None)
    if segments is None:
        return (getattr(result, "text", "") or "").strip()
    kept, dropped = [], 0
    for segment in segments:
        if (
            segment.no_speech_prob <= settings.stt_no_speech_prob_max
            and segment.avg_logprob >= settings.stt_avg_logprob_min
        ):
            kept.append(segment.text.strip())
        else:
            dropped += 1
    if dropped:
        logger.info("dropped %d likely-hallucinated STT segment(s)", dropped)
    return " ".join(part for part in kept if part).strip()


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

    # verbose_json (segment confidences for the hallucination gate) is a
    # whisper-1-only format; the gpt-4o-transcribe family rejects it.
    verbose = settings.stt_model.startswith("whisper")
    try:
        result = _client().audio.transcriptions.create(
            model=settings.stt_model,
            file=audio_file,
            language=language,
            prompt=settings.stt_prompt_ar or None,
            response_format="verbose_json" if verbose else "text",
            temperature=0.0,
        )
    except OpenAIError as exc:
        raise RuntimeError(f"STT request failed: {exc}") from exc

    if verbose:
        return _drop_hallucinated_segments(result)
    # response_format="text" yields a bare string; guard for SDK objects too.
    text = result if isinstance(result, str) else getattr(result, "text", "")
    return text.strip()
