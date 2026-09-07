"""User account management — password hashing and authentication.

Passwords are hashed with PBKDF2-SHA256 (150k iterations, 16-byte salt)
using the stdlib hashlib module. The default user directory is
bootstrapped on first authentication if the user table is empty, giving
a working login out of the box for the five RBAC roles.

Default credentials (bootstrap only — change in production):
- rm_ahmad / warba2025 (RM)
- risk_sara / warba2025 (Risk)
- cc_khalid / warba2025 (CreditCommittee)
- sb_omar / warba2025 (ShariahBoard)
- admin_system / warba2025 (Admin)
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import UserAccount

logger = logging.getLogger(__name__)

_PBKDF2_ITERATIONS = 150_000
_SALT_BYTES = 16

# Bootstrap directory used only when the user table is empty.
DEFAULT_USERS = [
    {"username": "rm_ahmad", "full_name": "Ahmad Al-Sabah", "email": "a.sabah@warbabank.com.kw", "role": "RM"},
    {"username": "risk_sara", "full_name": "Sara Al-Mutairi", "email": "s.mutairi@warbabank.com.kw", "role": "Risk"},
    {"username": "cc_khalid", "full_name": "Khalid Al-Fadhli", "email": "k.fadhli@warbabank.com.kw", "role": "CreditCommittee"},
    {"username": "sb_omar", "full_name": "Dr. Omar Al-Rashid", "email": "o.rashid@warbabank.com.kw", "role": "ShariahBoard"},
    {"username": "admin_system", "full_name": "System Administrator", "email": "admin@warbabank.com.kw", "role": "Admin"},
]
DEFAULT_PASSWORD = "warba2025"


def hash_password(password: str) -> str:
    """Hash a password with a random salt using PBKDF2-SHA256.

    Returns a string of the form "pbkdf2_sha256$iterations$salt_hex$hash_hex".
    """
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored PBKDF2 hash."""
    try:
        scheme, iterations, salt_hex, hash_hex = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        # Constant-time comparison
        return secrets.compare_digest(actual, expected)
    except (ValueError, AttributeError):
        return False


def ensure_default_users(db: Session) -> None:
    """Bootstrap the default user directory if the table is empty."""
    if db.query(UserAccount).count() > 0:
        return
    for spec in DEFAULT_USERS:
        db.add(UserAccount(
            username=spec["username"],
            full_name=spec["full_name"],
            email=spec["email"],
            role=spec["role"],
            password_hash=hash_password(DEFAULT_PASSWORD),
        ))
    db.flush()
    logger.info("Bootstrapped %d default user accounts", len(DEFAULT_USERS))


def authenticate_user(db: Session, username: str, password: str) -> Optional[UserAccount]:
    """Authenticate a user by username and password.

    Returns the UserAccount on success, None on failure. Boots the default
    directory on first use.
    """
    ensure_default_users(db)
    user = db.query(UserAccount).filter(UserAccount.username == username).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    return user


def create_user(
    db: Session,
    username: str,
    full_name: str,
    email: Optional[str],
    role: str,
    password: str,
) -> UserAccount:
    """Create a new user account with a hashed password.

    Raises:
        ValueError: If the username already exists or the role is invalid.
    """
    valid_roles = {"RM", "Risk", "CreditCommittee", "ShariahBoard", "Admin"}
    if role not in valid_roles:
        raise ValueError(f"Invalid role '{role}'. Valid: {sorted(valid_roles)}")
    if db.query(UserAccount).filter(UserAccount.username == username).first():
        raise ValueError(f"Username '{username}' already exists")

    user = UserAccount(
        username=username,
        full_name=full_name,
        email=email,
        role=role,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()
    return user
