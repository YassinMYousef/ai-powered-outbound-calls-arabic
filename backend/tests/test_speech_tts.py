"""Speech TTS (Sprint 2) — ElevenLabs request contract, HTTP mocked."""
import pytest

from app.config import settings
from app.speech import tts


class _FakeResponse:
    def __init__(self, status_code=200, content=b"audio", text="", chunks=None):
        self.status_code = status_code
        self.content = content
        self.text = text
        self.chunks = chunks or [content]
        self.iterated = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.content

    def iter_bytes(self):
        self.iterated = True
        yield from self.chunks


class _FakeClient:
    def __init__(self, sink: dict, response: _FakeResponse):
        self._sink = sink
        self._response = response

    def post(self, url, *, params, headers, json):
        self._sink.update(url=url, params=params, headers=headers, json=json)
        return self._response

    def stream(self, method, url, *, params, headers, json):
        self._sink.update(
            method=method,
            url=url,
            params=params,
            headers=headers,
            json=json,
        )
        return self._response


@pytest.fixture(autouse=True)
def _base_settings(monkeypatch):
    monkeypatch.setattr(settings, "tts_api_key", "xi-test-key")
    monkeypatch.setattr(settings, "elevenlabs_voice_id", "L10lEremDiJfPicq5CPh")
    monkeypatch.setattr(settings, "elevenlabs_model_id", "eleven_multilingual_v2")
    monkeypatch.setattr(settings, "elevenlabs_output_format", "mp3_44100_128")
    monkeypatch.setattr(settings, "elevenlabs_text_normalization", "auto")
    monkeypatch.setattr(settings, "elevenlabs_pronunciation_dictionary_id", "")
    monkeypatch.setattr(settings, "elevenlabs_pronunciation_dictionary_version_id", "")


def _patch(monkeypatch, sink, response=None):
    monkeypatch.setattr(tts, "_client", lambda: _FakeClient(sink, response or _FakeResponse()))


def test_synthesize_builds_expected_request(monkeypatch) -> None:
    sink: dict = {}
    _patch(monkeypatch, sink, _FakeResponse(content=b"MP3DATA"))

    audio = tts.synthesize("مرحبًا بك")

    assert audio == b"MP3DATA"
    assert sink["url"] == "/v1/text-to-speech/L10lEremDiJfPicq5CPh"
    assert sink["params"] == {"output_format": "mp3_44100_128"}
    assert sink["headers"]["xi-api-key"] == "xi-test-key"
    body = sink["json"]
    assert body["text"] == "مرحبًا بك"
    assert body["model_id"] == "eleven_multilingual_v2"
    assert body["apply_text_normalization"] == "auto"
    assert set(body["voice_settings"]) == {
        "stability", "similarity_boost", "style", "use_speaker_boost"
    }
    # No dictionary configured → no locator key at all.
    assert "pronunciation_dictionary_locators" not in body


def test_voice_override_changes_url(monkeypatch) -> None:
    sink: dict = {}
    _patch(monkeypatch, sink)
    tts.synthesize("نص", voice="OtherVoiceId")
    assert sink["url"] == "/v1/text-to-speech/OtherVoiceId"


def test_pronunciation_dictionary_locator_sent_when_both_ids_set(monkeypatch) -> None:
    sink: dict = {}
    monkeypatch.setattr(settings, "elevenlabs_pronunciation_dictionary_id", "dict_123")
    monkeypatch.setattr(settings, "elevenlabs_pronunciation_dictionary_version_id", "ver_9")
    _patch(monkeypatch, sink)

    tts.synthesize("نص")

    assert sink["json"]["pronunciation_dictionary_locators"] == [
        {"pronunciation_dictionary_id": "dict_123", "version_id": "ver_9"}
    ]


def test_partial_dictionary_config_sends_no_locator(monkeypatch) -> None:
    sink: dict = {}
    monkeypatch.setattr(settings, "elevenlabs_pronunciation_dictionary_id", "dict_123")
    monkeypatch.setattr(settings, "elevenlabs_pronunciation_dictionary_version_id", "")
    _patch(monkeypatch, sink)
    tts.synthesize("نص")
    assert "pronunciation_dictionary_locators" not in sink["json"]


def test_empty_text_raises(monkeypatch) -> None:
    _patch(monkeypatch, {})
    with pytest.raises(ValueError, match="non-empty"):
        tts.synthesize("   ")


def test_missing_api_key_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tts_api_key", "")
    _patch(monkeypatch, {})
    with pytest.raises(RuntimeError, match="TTS_API_KEY"):
        tts.synthesize("نص")


def test_non_200_raises(monkeypatch) -> None:
    _patch(monkeypatch, {}, _FakeResponse(status_code=401, text="unauthorized"))
    with pytest.raises(RuntimeError, match="401"):
        tts.synthesize("نص")


def test_synthesize_stream_builds_expected_request_and_yields_chunks(monkeypatch) -> None:
    sink: dict = {}
    response = _FakeResponse(chunks=[b"one", b"two"])
    _patch(monkeypatch, sink, response)

    chunks = list(tts.synthesize_stream("مرحبًا بك"))

    assert chunks == [b"one", b"two"]
    assert sink["method"] == "POST"
    assert sink["url"] == "/v1/text-to-speech/L10lEremDiJfPicq5CPh/stream"
    assert sink["params"] == {"output_format": "mp3_44100_128"}
    assert sink["headers"] == {"xi-api-key": "xi-test-key", "accept": "audio/*"}
    assert sink["json"]["text"] == "مرحبًا بك"
    assert sink["json"]["model_id"] == "eleven_multilingual_v2"
    assert sink["json"]["apply_text_normalization"] == "auto"


def test_synthesize_stream_empty_text_raises_before_http(monkeypatch) -> None:
    sink: dict = {}
    _patch(monkeypatch, sink)

    with pytest.raises(ValueError, match="non-empty"):
        tts.synthesize_stream("   ")

    assert sink == {}


def test_synthesize_stream_missing_api_key_raises_eagerly(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tts_api_key", "")
    _patch(monkeypatch, {})

    with pytest.raises(RuntimeError, match="TTS_API_KEY"):
        tts.synthesize_stream("نص")


def test_synthesize_stream_non_200_raises_without_yielding(monkeypatch) -> None:
    sink: dict = {}
    response = _FakeResponse(status_code=401, text="unauthorized", chunks=[b"must-not-yield"])
    _patch(monkeypatch, sink, response)

    with pytest.raises(RuntimeError, match="401"):
        list(tts.synthesize_stream("نص"))

    assert response.iterated is False
