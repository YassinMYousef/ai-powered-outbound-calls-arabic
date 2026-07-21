"""OAuth2 password flow + JWT bearer auth and role-based access control.

Module: Backend/Data. KB content is proprietary — chat/kb/report endpoints are
guarded with require_role and every access is written to audit_logs (data/audit.py).

Passwords are hashed with PBKDF2-HMAC-SHA256 from the standard library (no extra
dependency, no bcrypt 72-byte truncation footgun); tokens are signed with PyJWT
(already a dependency). Roles are hierarchical — admin > quality_manager > agent —
so require_role("agent") admits everyone and require_role("admin") admits admins
only, which is why a single injected role satisfies every guard it outranks.
"""
import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.data.db import get_db
from app.data.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# Higher number = more access. require_role compares against these, so a role is
# accepted for any guard whose minimum it meets or exceeds.
ROLE_LEVELS: dict[str, int] = {"agent": 1, "quality_manager": 2, "admin": 3}

_PBKDF2_ALGORITHM = "pbkdf2_sha256"
_PBKDF2_ROUNDS = 240_000


# --- Password hashing -----------------------------------------------------


def hash_password(password: str) -> str:
    """Return a self-describing PBKDF2 hash: 'pbkdf2_sha256$rounds$salt$hash'."""
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return "$".join(
        [
            _PBKDF2_ALGORITHM,
            str(_PBKDF2_ROUNDS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(derived).decode("ascii"),
        ]
    )


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check of `password` against a hash_password() string."""
    try:
        algorithm, rounds_str, salt_b64, hash_b64 = encoded.split("$")
        rounds = int(rounds_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    if algorithm != _PBKDF2_ALGORITHM:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(candidate, expected)


# --- JWT ------------------------------------------------------------------


def create_access_token(user: User) -> str:
    """Sign a short-lived bearer token carrying the user's id and role."""
    if not settings.jwt_secret or settings.jwt_secret == "change-me":
        # Refuse to mint forgeable tokens with the shipped default secret.
        raise RuntimeError("jwt_secret is unset/default — set it before issuing tokens")
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# --- Dependencies ---------------------------------------------------------

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Decode/validate the JWT and load the active user it names."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise _CREDENTIALS_EXC from exc
    subject = payload.get("sub")
    if subject is None:
        raise _CREDENTIALS_EXC
    try:
        user = db.get(User, int(subject))
    except (TypeError, ValueError) as exc:
        raise _CREDENTIALS_EXC from exc
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXC
    return user


def require_role(minimum_role: str):
    """Dependency factory: admit users whose role meets or exceeds `minimum_role`.

    Usage: `user: User = Depends(require_role("quality_manager"))`.
    """
    if minimum_role not in ROLE_LEVELS:
        raise ValueError(f"unknown role {minimum_role!r}")
    minimum_level = ROLE_LEVELS[minimum_role]

    def _dependency(user: User = Depends(get_current_user)) -> User:
        if ROLE_LEVELS.get(user.role, 0) < minimum_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"requires role '{minimum_role}' or higher",
            )
        return user

    return _dependency
