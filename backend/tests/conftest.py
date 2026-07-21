import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.data.auth import get_current_user
from app.data.db import get_db
from app.data.models import Base, User
from app.main import app


@pytest.fixture(autouse=True)
def _query_cache_disabled():
    """Keep every test hermetic — the RAG query cache touches Redis and Postgres.

    Cache tests re-enable the flag explicitly and fake those dependencies.
    Restores by hand rather than via the monkeypatch fixture: depending on
    monkeypatch here would reorder its teardown after per-file autouse fixtures
    (test_rag_embeddings' _fresh_client breaks on that).
    """
    original = settings.rag_query_cache_enabled
    settings.rag_query_cache_enabled = False
    yield
    settings.rag_query_cache_enabled = original


@pytest.fixture
def db_session():
    """In-memory SQLite session with the full schema — no Postgres needed."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    with TestingSession() as session:
        yield session
    engine.dispose()


@pytest.fixture
def anon_client(db_session) -> TestClient:
    """A client with NO authenticated user — for exercising the 401/403 guards
    and the real login → token flow (see tests/test_auth.py)."""
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(db_session) -> TestClient:
    """Authenticated client: every request runs as a seeded admin.

    Endpoint routes are now RBAC-guarded (data/auth.require_role), so this fixture
    injects an admin via a get_current_user override — that keeps the module-focused
    endpoint tests testing their endpoint, not the login dance. The guard machinery
    itself (token decode, role hierarchy, 401/403) is covered end-to-end by
    tests/test_auth.py through anon_client.
    """
    def _get_db():
        yield db_session

    admin = User(
        username="test-admin",
        email="test-admin@example.com",
        full_name="اختبار",
        hashed_password="x",  # never verified — this client bypasses login
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
