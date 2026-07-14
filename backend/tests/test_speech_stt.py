"""Speech STT (Sprint 1) — Whisper wrapper contract, provider mocked."""
import io

import pytest
from openai import OpenAIError

from app.config import settings
from app.speech import stt


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
    _patch_client(monkeypatch, sink, "  نعم خلصت الإجراء  ")
    monkeypatch.setattr(settings, "stt_model", "whisper-1")
    monkeypatch.setattr(settings, "stt_prompt_ar", "مكالمة متابعة بالعامية المصرية")

    result = stt.transcribe(b"RIFFfake-wav-bytes", language="ar")

    assert result == "نعم خلصت الإجراء"  # stripped
    assert sink["model"] == "whisper-1"
    assert sink["language"] == "ar"
    assert sink["prompt"] == "مكالمة متابعة بالعامية المصرية"
    assert sink["response_format"] == "text"
    assert sink["temperature"] == 0.0
    # file must be an uploadable with a .wav name so the SDK infers the format
    assert isinstance(sink["file"], io.BytesIO)
    assert sink["file"].name.endswith(".wav")


def test_transcribe_empty_prompt_sends_none(monkeypatch) -> None:
    sink: dict = {}
    _patch_client(monkeypatch, sink, "text")
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
