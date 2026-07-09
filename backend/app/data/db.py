"""Engine and session factory. Alembic migrations to be added once schemas settle.

Module: Backend/Data.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    """FastAPI dependency yielding a request-scoped session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
