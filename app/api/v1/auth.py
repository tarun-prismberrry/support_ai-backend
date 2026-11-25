"""
Authentication Routes: Lean JWT Login and User Context Resolution (/auth/me).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import UserContext, get_current_user
from app.core.security import create_access_token, verify_password
from app.models.tenant import Organization
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate user credentials via bcrypt and issue a Lean JWT access token.
    """
    normalized_email = payload.email.strip().lower()

    stmt = select(User).where(User.email == normalized_email)
    if payload.org_slug:
        stmt = stmt.join(Organization, User.org_id == Organization.id).where(
            Organization.slug == payload.org_slug.strip().lower()
        )

    result = await db.execute(stmt)
    users = list(result.scalars().all())

    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multiple organizations found for this email. Please specify 'org_slug'.",
        )

    user = users[0] if users else None

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user_id=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserContext, status_code=status.HTTP_200_OK)
async def get_me(
    current_user: UserContext = Depends(get_current_user),
) -> UserContext:
    """
    Resolve caller's full identity, role, permissions, and authorized KB tiers.
    Matches CONTRACTS.md Section 2.C.
    """
    return current_user