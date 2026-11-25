"""
Authentication Pydantic Schemas for Login and Token Issuance.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials payload for POST /auth/login."""

    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)
    org_slug: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional organization slug when the same email belongs to multiple tenants",
    )


class TokenResponse(BaseModel):
    """Lean JWT bearer token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int