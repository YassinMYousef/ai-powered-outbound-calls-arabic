"""Telephony webhook loop — TwiML, dialog persistence, and streamed audio."""
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.config import settings
from app.data.models import CallLog
from app.speech.replies import repeat_question_text
from app.telephony import audio_store, client as telephony_client, webhooks


@pytest.fixture(autouse=True)
def _deferred_speech(monkeypatch) -> None:
    monkeypatch.setattr(audio_store, "store_text", lambda text_ar: "tok")
    monkeypatch.setattr(
        audio_store,
        "play_url",
        lambda token: f"http://testserver/telephony/audio/{token}",
    )


def _seed_call(db_session: Session, *, ticket_id: str = "T-123") -> CallLog:
    call = CallLog(customer_phone="+201000000000", ticket_id=ticket_id)
    db_session.add(call)
    db_session.commit()
    return call


def test_voice_returns_dynamic_greeting_record_and_redirect(
    client: TestClient,
    db_session: Session,
) -> None:
    call = _seed_call(db_session)

    response = client.post(f"/telephony/voice?call_id={call.id}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    body = response.text
    assert "<Play>http://testserver/telephony/audio/tok</Play>" in body
    assert "<Record" in body
    assert (
        f'action="/telephony/gather?call_id={call.id}&amp;turn=0"'
        in body
    )
    assert f'maxLength="{settings.record_max_length_seconds}"' in body
    assert f'timeout="{settings.record_silence_timeout_seconds}"' in body
    assert "<Redirect" in body
    assert body.index("<Record") < body.index("<Redirect")


def test_voice_falls_back_to_say_with_dynamic_ticket(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    call = _seed_call(db_session, ticket_id="CASE-77")

    def fail_store(text_ar: str) -> str:
        raise RuntimeError("redis down")

    monkeypatch.setattr(audio_store, "store_text", fail_store)

    response = client.post(f"/telephony/voice?call_id={call.id}")

    assert response.status_code == 200
    assert '<Say language="arb" voice="Polly.Zeina">' in response.text
    assert "CASE-77" in response.text
    assert "هل تم حل مشكلتك بنجاح؟" in response.text


def test_voice_without_call_id_produces_working_gather_action(client: TestClient) -> None:
    voice_response = client.post("/telephony/voice")
    root = ElementTree.fromstring(voice_response.text)
    action = root.find("Record").attrib["action"]

    assert "call_id" not in action
    assert action == "/telephony/gather?turn=0"

    gather_response = client.post(action, data={"SpeechResult": "نعم"})

    assert gather_response.status_code == 200
    assert "<Hangup" in gather_response.text


def test_gather_yes_marks_call_resolved(
    client: TestClient,
    db_session: Session,
) -> None:
    call = _seed_call(db_session)

    response = client.post(
        f"/telephony/gather?call_id={call.id}&turn=0",
        data={"SpeechResult": "نعم"},
    )

    assert response.status_code == 200
    assert "<Play>" in response.text
    assert "<Hangup" in response.text
    db_session.refresh(call)
    assert call.outcome == "resolved"
    assert "[turn 0]" in (call.transcript or "")


def test_gather_no_offers_help_and_records_next_turn(
    client: TestClient,
    db_session: Session,
) -> None:
    call = _seed_call(db_session)

    response = client.post(
        f"/telephony/gather?call_id={call.id}&turn=0",
        data={"SpeechResult": "لا"},
    )

    assert response.status_code == 200
    assert "<Play>" in response.text
    assert (
        f'action="/telephony/gather?call_id={call.id}&amp;turn=1"'
        in response.text
    )


def test_gather_escalates_to_configured_agent(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    call = _seed_call(db_session)
    monkeypatch.setattr(settings, "human_agent_number", "+12025550123")
    monkeypatch.setattr(settings, "twilio_from_number", "+12025550999")

    response = client.post(
        f"/telephony/gather?call_id={call.id}&turn=2",
        data={"SpeechResult": "غير متأكد"},
    )

    assert response.status_code == 200
    assert "<Dial" in response.text
    assert "+12025550123" in response.text
    assert "<Hangup" in response.text
    db_session.refresh(call)
    assert call.outcome == "transferred"


def test_gather_escalation_without_agent_apologizes_and_hangs_up(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    call = _seed_call(db_session)
    monkeypatch.setattr(settings, "human_agent_number", "")
    spoken: list[str] = []
    monkeypatch.setattr(
        audio_store,
        "store_text",
        lambda text_ar: spoken.append(text_ar) or "tok",
    )

    response = client.post(
        f"/telephony/gather?call_id={call.id}&turn=2",
        data={"SpeechResult": "لا"},
    )

    assert response.status_code == 200
    assert "<Dial" not in response.text
    assert "<Hangup" in response.text
    assert spoken and "نعتذر" in spoken[-1]
    db_session.refresh(call)
    assert call.outcome == "unresolved"


def test_gather_fetches_and_transcribes_recording(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    call = _seed_call(db_session)
    transcribed: list[bytes] = []
    monkeypatch.setattr(telephony_client, "fetch_recording_wav", lambda url: b"wav")
    monkeypatch.setattr(webhooks.audio, "wav_to_stt_wav", lambda wav: b"wav16")
    monkeypatch.setattr(
        webhooks.stt,
        "transcribe",
        lambda wav: transcribed.append(wav) or "نعم",
    )

    response = client.post(
        f"/telephony/gather?call_id={call.id}&turn=0",
        data={"RecordingUrl": "https://api.twilio.com/recording"},
    )

    assert response.status_code == 200
    assert "<Hangup" in response.text
    assert transcribed == [b"wav16"]
    db_session.refresh(call)
    assert call.outcome == "resolved"


def test_gather_no_input_repeats_question(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    call = _seed_call(db_session)
    spoken: list[str] = []
    monkeypatch.setattr(
        audio_store,
        "store_text",
        lambda text_ar: spoken.append(text_ar) or "tok",
    )

    response = client.post(f"/telephony/gather?call_id={call.id}&turn=0")

    assert response.status_code == 200
    assert spoken == [repeat_question_text(webhooks._greeting_ctx(call))]
    assert (
        f'action="/telephony/gather?call_id={call.id}&amp;turn=1"'
        in response.text
    )


def test_gather_recording_failure_repeats_question(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    call = _seed_call(db_session)

    def fail_fetch(url: str) -> bytes:
        raise RuntimeError("recording unavailable")

    monkeypatch.setattr(telephony_client, "fetch_recording_wav", fail_fetch)

    response = client.post(
        f"/telephony/gather?call_id={call.id}&turn=0",
        data={"RecordingUrl": "https://api.twilio.com/recording"},
    )

    assert response.status_code == 200
    assert (
        f'action="/telephony/gather?call_id={call.id}&amp;turn=1"'
        in response.text
    )


def test_gather_same_turn_appends_transcript_once(
    client: TestClient,
    db_session: Session,
) -> None:
    call = _seed_call(db_session)
    url = f"/telephony/gather?call_id={call.id}&turn=0"

    assert client.post(url, data={"SpeechResult": "لا"}).status_code == 200
    assert client.post(url, data={"SpeechResult": "لا"}).status_code == 200

    db_session.refresh(call)
    assert (call.transcript or "").count("[turn 0]") == 1


def test_audio_endpoint_streams_and_caches_completed_audio(
    client: TestClient,
    monkeypatch,
) -> None:
    cached: list[tuple[str, bytes]] = []
    monkeypatch.setattr(audio_store, "fetch_text", lambda token: "مرحبًا")
    monkeypatch.setattr(audio_store, "get_cached_audio", lambda text_ar: None)
    monkeypatch.setattr(audio_store, "audio_content_type", lambda: "audio/mpeg")
    monkeypatch.setattr(webhooks.tts, "synthesize_stream", lambda text_ar: iter([b"a", b"b"]))
    monkeypatch.setattr(
        audio_store,
        "cache_audio",
        lambda text_ar, audio: cached.append((text_ar, audio)),
    )

    response = client.get("/telephony/audio/tok")

    assert response.status_code == 200
    assert response.content == b"ab"
    assert response.headers["content-type"] == "audio/mpeg"
    assert cached == [("مرحبًا", b"ab")]


def test_audio_endpoint_returns_cache_hit_without_synthesis(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(audio_store, "fetch_text", lambda token: "مرحبًا")
    monkeypatch.setattr(audio_store, "get_cached_audio", lambda text_ar: b"hit")
    monkeypatch.setattr(audio_store, "audio_content_type", lambda: "audio/mpeg")

    def fail_synthesis(text_ar: str):
        pytest.fail("synthesize_stream must not run for a cache hit")

    monkeypatch.setattr(webhooks.tts, "synthesize_stream", fail_synthesis)

    response = client.get("/telephony/audio/tok")

    assert response.status_code == 200
    assert response.content == b"hit"


def test_audio_endpoint_missing_token_returns_404(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(audio_store, "fetch_text", lambda token: None)

    response = client.get("/telephony/audio/missing")

    assert response.status_code == 404


def test_audio_endpoint_redis_failure_returns_503(
    client: TestClient,
    monkeypatch,
) -> None:
    def fail_fetch(token: str) -> str | None:
        raise RedisError("redis unavailable")

    monkeypatch.setattr(audio_store, "fetch_text", fail_fetch)

    response = client.get("/telephony/audio/tok")

    assert response.status_code == 503


def test_audio_endpoint_synthesis_failure_before_first_chunk_returns_404(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(audio_store, "fetch_text", lambda token: "مرحبًا")
    monkeypatch.setattr(audio_store, "get_cached_audio", lambda text_ar: None)
    monkeypatch.setattr(audio_store, "audio_content_type", lambda: "audio/mpeg")

    def fail_synthesis(text_ar: str):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(webhooks.tts, "synthesize_stream", fail_synthesis)

    response = client.get("/telephony/audio/tok")

    assert response.status_code == 404


def test_audio_cache_key_fingerprints_every_synthesis_setting(monkeypatch) -> None:
    text_ar = "مرحبًا"
    baseline = audio_store._audio_key(text_ar)
    setting_names = (
        "elevenlabs_voice_id",
        "elevenlabs_output_format",
        "elevenlabs_model_id",
        "elevenlabs_text_normalization",
        "elevenlabs_pronunciation_dictionary_id",
        "elevenlabs_pronunciation_dictionary_version_id",
        "elevenlabs_stability",
        "elevenlabs_similarity_boost",
        "elevenlabs_style",
        "elevenlabs_use_speaker_boost",
    )

    for name in setting_names:
        original = getattr(settings, name)
        if isinstance(original, bool):
            changed = not original
        elif isinstance(original, float):
            changed = original + 0.123456
        else:
            changed = f"{original}-changed"
        monkeypatch.setattr(settings, name, changed)
        assert audio_store._audio_key(text_ar) != baseline
        monkeypatch.setattr(settings, name, original)

    assert audio_store._audio_key(text_ar) == baseline
    assert audio_store._audio_key(f"{text_ar} مختلف") != baseline


def test_status_acks_without_body(client: TestClient) -> None:
    response = client.post(
        "/telephony/status?call_id=1",
        data={"CallSid": "CA123", "CallStatus": "completed", "CallDuration": "7"},
    )

    assert response.status_code == 204
