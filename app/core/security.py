"""Security module: JWT authentication and RBAC enforcement.

Provides JWT token creation/verification, user identity model with roles,
and FastAPI dependencies for role-based access control.

Design decision: Roles are attached to the user at token creation time
(from the auth system or seed data). Every API endpoint validates the
token and checks the required role before processing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)


class UserIdentity(BaseModel):
    """Authenticated user identity extracted from JWT."""

    user_id: str
    username: str
    full_name: str
    role: str  # RM, Risk, CreditCommittee, ShariahBoard, Admin
    acl_groups: List[str] = Field(default_factory=list)


def create_access_token(
    user_id: str,
    username: str,
    full_name: str,
    role: str,
    acl_groups: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: Unique user identifier.
        username: Login username.
        full_name: Display name.
        role: User's role (RM, Risk, CreditCommittee, ShariahBoard, Admin).
        acl_groups: ACL groups for RAG filtering.
        expires_delta: Custom expiration (defaults to settings).

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_expiration_minutes)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "full_name": full_name,
        "role": role,
        "acl_groups": acl_groups or [],
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> UserIdentity:
    """Verify and decode a JWT token.

    Args:
        token: The JWT token string.

    Returns:
        UserIdentity with the decoded claims.

    Raises:
        HTTPException: If the token is invalid or expired.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return UserIdentity(
            user_id=payload["sub"],
            username=payload["username"],
            full_name=payload["full_name"],
            role=payload["role"],
            acl_groups=payload.get("acl_groups", []),
        )
    except JWTError as e:
        logger.warning("JWT verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> UserIdentity:
    """FastAPI dependency: extract and validate the current user from JWT."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(credentials.credentials)


def require_roles(*roles: str):
    """FastAPI dependency factory: require one of the specified roles.

    Usage:
        @router.get("/endpoint", dependencies=[Depends(require_roles("Admin", "RM"))])
    """
    def _check(user: UserIdentity = Depends(get_current_user)) -> UserIdentity:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not authorized. Required: {roles}",
            )
        return user
    return _check


def can_approve_section(user_role: str, section_key: str) -> bool:
    """Check if a user's role can approve a specific section type.

    Args:
        user_role: The user's role.
        section_key: The memo section key.

    Returns:
        True if the user is authorized to approve this section.
    """
    from app.core.business_config import get_section_approval_roles

    allowed_roles = get_section_approval_roles(section_key)
    return user_role in allowed_roles
