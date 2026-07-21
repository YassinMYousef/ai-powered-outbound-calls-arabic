"""Auth + RBAC: password hashing, the login→token→access flow, and the guards."""
import pytest

from app.config import settings
from app.data.auth import (
    ROLE_LEVELS,
    create_access_token,
    hash_password,
    verify_password,
)
from app.data.models import AuditLog, User


@pytest.fixture(autouse=True)
def _known_jwt_secret():
    """Sign/verify tokens with a deterministic secret regardless of the env."""
    original = settings.jwt_secret
    settings.jwt_secret = "test-secret-not-change-me-0123456789abcdef"
    yield
    settings.jwt_secret = original


def _make_user(db, username="agent1", role="agent", password="pw-12345"):
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name="مستخدم",
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _token(anon_client, username, password="pw-12345"):
    resp = anon_client.post(
        "/api/auth/token", data={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# --- Password hashing ------------------------------------------------------


def test_hash_password_roundtrip():
    encoded = hash_password("سر-قوي-123")
    assert encoded.startswith("pbkdf2_sha256$")
    assert verify_password("سر-قوي-123", encoded)
    assert not verify_password("wrong", encoded)


def test_hash_password_is_salted():
    assert hash_password("same") != hash_password("same")


def test_verify_password_rejects_garbage():
    assert not verify_password("x", "not-a-valid-hash")


# --- Login flow ------------------------------------------------------------


def test_login_success_returns_bearer_token(anon_client, db_session):
    _make_user(db_session, "agent1", "agent")
    resp = anon_client.post("/api/auth/token", data={"username": "agent1", "password": "pw-12345"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "agent"
    assert body["access_token"]


def test_login_wrong_password_is_401(anon_client, db_session):
    _make_user(db_session, "agent1", "agent")
    resp = anon_client.post("/api/auth/token", data={"username": "agent1", "password": "nope"})
    assert resp.status_code == 401


def test_login_unknown_user_is_401(anon_client):
    resp = anon_client.post("/api/auth/token", data={"username": "ghost", "password": "x"})
    assert resp.status_code == 401


def test_inactive_user_cannot_log_in(anon_client, db_session):
    user = _make_user(db_session, "agent1", "agent")
    user.is_active = False
    db_session.commit()
    resp = anon_client.post("/api/auth/token", data={"username": "agent1", "password": "pw-12345"})
    assert resp.status_code == 401


def test_me_returns_current_user(anon_client, db_session):
    _make_user(db_session, "agent1", "agent")
    token = _token(anon_client, "agent1")
    resp = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "agent1"
    assert resp.json()["role"] == "agent"


# --- Guards ----------------------------------------------------------------


def test_guarded_route_without_token_is_401(anon_client):
    assert anon_client.post("/api/chat/query", json={"query": "مرحبا"}).status_code == 401


def test_garbage_token_is_401(anon_client):
    resp = anon_client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


def test_agent_cannot_reach_quality_manager_route(anon_client, db_session):
    _make_user(db_session, "agent1", "agent")
    token = _token(anon_client, "agent1")
    # /api/reports/kpis requires quality_manager
    resp = anon_client.get("/api/reports/kpis", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_role_hierarchy_admin_outranks_all(anon_client, db_session):
    _make_user(db_session, "boss", "admin")
    token = _token(anon_client, "boss")
    headers = {"Authorization": f"Bearer {token}"}
    # admin clears an agent-min guard and a quality_manager-min guard alike
    assert anon_client.get("/api/calls", headers=headers).status_code == 200
    assert anon_client.get("/api/reports/kpis", headers=headers).status_code == 200


def test_quality_manager_reaches_reports_but_not_admin_only(anon_client, db_session):
    _make_user(db_session, "qm", "quality_manager")
    token = _token(anon_client, "qm")
    headers = {"Authorization": f"Bearer {token}"}
    assert anon_client.get("/api/reports/kpis", headers=headers).status_code == 200
    # KB upload is admin-only; a manager is forbidden
    resp = anon_client.post(
        "/api/kb/documents", headers=headers, files={"file": ("x.txt", b"hi", "text/plain")}
    )
    assert resp.status_code == 403


def test_role_levels_are_ordered():
    assert ROLE_LEVELS["admin"] > ROLE_LEVELS["quality_manager"] > ROLE_LEVELS["agent"]


def test_create_access_token_refuses_default_secret(db_session):
    settings.jwt_secret = "change-me"
    user = _make_user(db_session, "agent1", "agent")
    with pytest.raises(RuntimeError):
        create_access_token(user)


# --- Audit trail -----------------------------------------------------------


def test_chat_query_writes_audit_log(client, db_session, monkeypatch):
    """The authenticated `client` (admin) hits chat; an audit row is written."""
    from app.conversation.rag import answer as answer_module

    monkeypatch.setattr(
        answer_module, "answer", lambda *a, **k: {"answer": "جواب", "sources": []}
    )
    resp = client.post("/api/chat/query", json={"query": "ما هي الإجراءات؟"})
    assert resp.status_code == 200
    rows = db_session.query(AuditLog).filter(AuditLog.action == "chat.query").all()
    assert len(rows) == 1
    assert rows[0].resource_type == "chat_session"
