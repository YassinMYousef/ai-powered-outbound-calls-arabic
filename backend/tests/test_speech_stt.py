"""Speech STT (Sprint 1) — Whisper wrapper contract, provider mocked."""
import io
from types import SimpleNamespace

import pytest
from openai import OpenAIError

from app.config import settings
from app.speech import stt


def _verbose_result(*segments: tuple[str, float, float]):
    """Build a fake verbose_json response: (text, no_speech_prob, avg_logprob)."""
    return SimpleNamespace(
        text=" ".join(text for text, _, _ in segments),
        segments=[
            SimpleNamespace(text=text, no_speech_prob=nsp, avg_logprob=alp)
            for text, nsp, alp in segments
        ],
    )


class _FakeTranscriptions:
    def __init__(self, sink: dict, result):
        self._sink = sink
        self._result = result

    def create(self, **kwargs):
        self._sink.update(kwargs)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakeClient:
    def __init__(self, sink: dict, result):
        self.audio = type("Audio", (), {"transcriptions": _FakeTranscriptions(sink, result)})()


def _patch_client(monkeypatch, sink, result):
    monkeypatch.setattr(stt, "_client", lambda: _FakeClient(sink, result))


def test_transcribe_passes_expected_params(monkeypatch) -> None:
    sink: dict = {}
    _patch_client(monkeypatch, sink, _verbose_result(("  نعم خلصت الإجراء  ", 0.1, -0.2)))
    monkeypatch.setattr(settings, "stt_model", "whisper-1")
    monkeypatch.setattr(settings, "stt_prompt_ar", "مكالمة متابعة بالعامية المصرية")

    result = stt.transcribe(b"RIFFfake-wav-bytes", language="ar")

    assert result == "نعم خلصت الإجراء"  # stripped
    assert sink["model"] == "whisper-1"
    assert sink["language"] == "ar"
    assert sink["prompt"] == "مكالمة متابعة بالعامية المصرية"
    # whisper-1 requests segment confidences for the hallucination gate
    assert sink["response_format"] == "verbose_json"
    assert sink["temperature"] == 0.0
    # file must be an uploadable with a .wav name so the SDK infers the format
    assert isinstance(sink["file"], io.BytesIO)
    assert sink["file"].name.endswith(".wav")


def test_transcribe_drops_hallucinated_segments(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_model", "whisper-1")
    _patch_client(
        monkeypatch,
        {},
        _verbose_result(
            ("اه هنبنوه كده بقى", 0.9, -0.4),   # silence: no_speech_prob too high
            ("نعم خلصت", 0.1, -0.3),            # confident real speech — kept
            ("تعالوا بقى بقى", 0.2, -1.8),       # gibberish: avg_logprob too low
        ),
    )
    assert stt.transcribe(b"bytes") == "نعم خلصت"


def test_transcribe_all_noise_returns_empty(monkeypatch) -> None:
    # Pure hallucination must become "" so dialog maps it to Intent.UNKNOWN
    # instead of a fabricated YES marking the call resolved.
    monkeypatch.setattr(settings, "stt_model", "whisper-1")
    _patch_client(monkeypatch, {}, _verbose_result(("اه هنبنوه كده بقى", 0.9, -1.5)))
    assert stt.transcribe(b"bytes") == ""


def test_transcribe_non_whisper_model_uses_text_format(monkeypatch) -> None:
    sink: dict = {}
    _patch_client(monkeypatch, sink, "  نعم  ")
    monkeypatch.setattr(settings, "stt_model", "gpt-4o-transcribe")
    assert stt.transcribe(b"bytes") == "نعم"
    assert sink["response_format"] == "text"


def test_transcribe_empty_prompt_sends_none(monkeypatch) -> None:
    sink: dict = {}
    _patch_client(monkeypatch, sink, _verbose_result(("text", 0.0, 0.0)))
    monkeypatch.setattr(settings, "stt_prompt_ar", "")
    stt.transcribe(b"bytes")
    assert sink["prompt"] is None


def test_transcribe_empty_audio_short_circuits(monkeypatch) -> None:
    # Must not touch the client at all.
    monkeypatch.setattr(stt, "_client", lambda: pytest.fail("client called on empty audio"))
    assert stt.transcribe(b"") == ""


def test_transcribe_wraps_provider_error(monkeypatch) -> None:
    _patch_client(monkeypatch, {}, OpenAIError("boom"))
    with pytest.raises(RuntimeError, match="STT request failed"):
        stt.transcribe(b"bytes")
