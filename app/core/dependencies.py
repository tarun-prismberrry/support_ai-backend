"""
FastAPI Dependencies for Authentication, Tenant Context Injection, and Dynamic RBAC.
"""

from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db, set_db_tenant_context
from app.core.redis import get_redis_client
from app.core.security import decode_access_token
from app.models.user import User

settings = get_settings()


class UserContext(BaseModel):
    """
    Authenticated User Context representing the resolved identity of the caller.
    Matches the GET /auth/me team contract.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    org_id: uuid.UUID
    customer_id: Optional[uuid.UUID] = None
    role: str
    permissions: list[str]
    authorized_kb_tiers: list[str]

    def has_permission(self, permission: str) -> bool:
        """Verify if caller possesses specific permission or administrative wildcard."""
        if "*" in self.permissions:
            return True
        return permission in self.permissions


def resolve_kb_tiers(permissions: list[str]) -> list[str]:
    """Calculate authorized KB access tiers based on role permissions."""
    if "*" in permissions:
        return ["public", "internal_staff", "admin_only"]
    tiers: list[str] = []
    if "kb.read:public" in permissions:
        tiers.append("public")
    if "kb.read:internal_staff" in permissions:
        tiers.append("internal_staff")
    if "kb.read:admin_only" in permissions:
        tiers.append("admin_only")
    return tiers


# Bearer token extractor for OpenAPI Swagger and microservice requests
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserContext:
    """
    Extract and decode Lean JWT access token, query database for active user and role,
    set PostgreSQL Row-Level Security tenant context, and return UserContext.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # In Lean JWT (CONTRACTS.md), user_id is in "user_id" or "sub"
    raw_user_id = payload.get("user_id") or payload.get("sub")
    if not raw_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identity claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(str(raw_user_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token contains malformed user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Cache-Aside Check in Redis (<0.5ms fast path)
    redis_key = f"cache:user:{user_uuid}"
    try:
        redis_client = get_redis_client()
        cached_data = await redis_client.get(redis_key)
        if cached_data:
            user_data = json.loads(
                cached_data.decode("utf-8") if isinstance(cached_data, bytes) else cached_data
            )
            user_context = UserContext.model_validate(user_data)
            # Crucial: Apply PostgreSQL RLS tenant context for this request's DB transaction
            await set_db_tenant_context(db, user_context.org_id)
            return user_context
    except Exception:
        # Graceful degradation: If Redis is unavailable, fall back to DB lookup seamlessly
        pass

    # 2. Cache Miss: Query PostgreSQL with preloaded role and customer profiles
    stmt = (
        select(User)
        .options(selectinload(User.role), selectinload(User.customer))
        .where(User.id == user_uuid)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no role assigned",
        )

    # Set PostgreSQL Row-Level Security (RLS) tenant context on this transaction!
    await set_db_tenant_context(db, user.org_id)

    permissions: list[str] = user.role.permissions or []
    customer_id = user.customer.id if user.customer else None

    user_context = UserContext(
        id=user.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        org_id=user.org_id,
        customer_id=customer_id,
        role=user.role.name,
        permissions=permissions,
        authorized_kb_tiers=resolve_kb_tiers(permissions),
    )

    # 3. Populate Redis Cache with TTL (Look-Aside write)
    try:
        redis_client = get_redis_client()
        await redis_client.set(
            redis_key,
            user_context.model_dump_json(),
            ex=settings.USER_CACHE_TTL_SECONDS,
        )
    except Exception:
        pass

    return user_context


async def invalidate_user_cache(user_id: uuid.UUID | str) -> None:
    """
    Invalidates cached UserContext in Redis.
    Must be called whenever user role, permissions, or active status change.
    """
    try:
        redis_client = get_redis_client()
        await redis_client.delete(f"cache:user:{user_id}")
    except Exception:
        pass


def require_permission(required_permission: str):
    """
    Dependency factory that verifies caller possesses the required permission.
    Supports administrative wildcard ('*').
    """
    async def permission_checker(
        current_user: UserContext = Depends(get_current_user),
    ) -> UserContext:
        if not current_user.has_permission(required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: missing required permission '{required_permission}'",
            )
        return current_user

    return permission_checker