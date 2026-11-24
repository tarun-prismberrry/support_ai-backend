"""
Security, Cryptography, and Token Management.
Handles bcrypt password hashing and RFC 7519 Lean JWT creation/validation.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()


class AuthError(Exception):
    """Raised when authentication or token verification fails."""
    def __init__(self, message: str, code: str = "UNAUTHORIZED"):
        self.message = message
        self.code = code
        super().__init__(message)


# ── Password Hashing & Verification (bcrypt) ──────────────────────────────────

def hash_password(plain_password: str) -> str:
    """Hash a password using bcrypt with a randomly generated salt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an existing bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ── JWT Token Minting & Decoding ─────────────────────────────────────────────

def create_access_token(
    user_id: UUID | str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Mints a signed Lean JWT access token.
    Carries only verified identity ('sub' and 'user_id') to support dynamic RBAC
    and instant permission revocation.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Cryptographically verifies a JWT token.
    Enforces algorithm pinning (HS256) and validates exp, iss, and aud.
    Raises AuthError on expired or tampered tokens.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Token has expired", code="UNAUTHORIZED") from e
    except jwt.InvalidTokenError as e:
        raise AuthError(f"Invalid token: {e}", code="UNAUTHORIZED") from e