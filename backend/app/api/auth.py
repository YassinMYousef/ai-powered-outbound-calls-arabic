"""Authentication endpoints — OAuth2 password login and the current-user probe.

Module: Backend/Data. POST /api/auth/token exchanges username+password for a JWT
bearer token; send it as `Authorization: Bearer <token>` to every guarded route.
Users are provisioned out of band (seed script / admin tooling), not self-signup.
"""
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.auth import create_access_token, get_current_user, verify_password
from app.data.db import get_db
from app.data.models import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/token")
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> dict:
    """Exchange username + password for a JWT access token."""
    user = db.execute(select(User).where(User.username == form.username)).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(form.password, user.hashed_password):
        # One message for every failure mode — never reveal which users exist.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user.last_login_at = datetime.now(UTC)
    db.commit()
    logger.info("user %s logged in (role=%s)", user.username, user.role)
    return {"access_token": create_access_token(user), "token_type": "bearer", "role": user.role}


@router.get("/me")
def read_me(user: User = Depends(get_current_user)) -> dict:
    """Return the authenticated user — the frontend uses this to gate routes."""
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
    }
