from fastapi.testclient import TestClient

from app.telephony.webhooks import GREETING_AR


def test_voice_returns_arabic_twiml(client: TestClient) -> None:
    response = client.post("/telephony/voice")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    body = response.text
    assert "<Response>" in body
    assert 'voice="Polly.Zeina"' in body
    assert GREETING_AR in body


def test_status_acks_without_body(client: TestClient) -> None:
    response = client.post(
        "/telephony/status?call_id=1",
        data={"CallSid": "CA123", "CallStatus": "completed", "CallDuration": "7"},
    )

    assert response.status_code == 204
