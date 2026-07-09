"""OAuth2 + role-based access control for KB data and reporting endpoints.

Module: Backend/Data. KB content is proprietary — chat/kb/report endpoints
get guarded with require_role once this lands, and access is audit-logged.
"""
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Decode and validate the JWT; return the user with their roles."""
    raise NotImplementedError


def require_role(role: str):
    """Dependency factory guarding role-restricted endpoints."""
    raise NotImplementedError
