"""
Authentication & RBAC Tests (CONTRACTS.md Section 3.A & 3.B).
Verifies /auth/login, /auth/me, invalid credentials, and Redis Cache-Aside behavior.
"""

from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.dependencies import invalidate_user_cache
from app.core.redis import get_redis_client

settings = get_settings()
ALICE_USER_ID = uuid.UUID("aaaaaaa1-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    """Valid credentials must return 200 OK with access_token and token_type."""
    response = await client.post(
        "/auth/login",
        json={"email": "alice@orga.com", "password": "Password123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient) -> None:
    """Invalid password must return 401 UNAUTHORIZED with standardized error envelope."""
    response = await client.post(
        "/auth/login",
        json={"email": "alice@orga.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "Invalid email or password" in data["error"]["message"]


@pytest.mark.asyncio
async def test_auth_me_admin_alice(client: AsyncClient, alice_headers: dict[str, str]) -> None:
    """Alice (/auth/me) must resolve as Org_Admin with wildcard and all 3 KB tiers."""
    response = await client.get("/auth/me", headers=alice_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "alice@orga.com"
    assert data["role"] == "Org_Admin"
    assert data["permissions"] == ["*"]
    assert set(data["authorized_kb_tiers"]) == {"public", "internal_staff", "admin_only"}


@pytest.mark.asyncio
async def test_auth_me_customer_charlie(client: AsyncClient, charlie_headers: dict[str, str]) -> None:
    """Charlie (/auth/me) must resolve as End_Customer with customer_id and public KB tier only."""
    response = await client.get("/auth/me", headers=charlie_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "charlie@customer.com"
    assert data["role"] == "End_Customer"
    assert data["customer_id"] is not None
    assert data["authorized_kb_tiers"] == ["public"]


@pytest.mark.asyncio
async def test_redis_user_session_cache_aside(client: AsyncClient, alice_headers: dict[str, str]) -> None:
    """Verifies that /auth/me caches user profile in Redis with TTL and purges on invalidation."""
    redis_client = get_redis_client()
    redis_key = f"cache:user:{ALICE_USER_ID}"

    # 1. Clear key to force initial cache miss
    await redis_client.delete(redis_key)

    # 2. Call /auth/me -> Populates Redis Cache
    resp1 = await client.get("/auth/me", headers=alice_headers)
    assert resp1.status_code == 200

    # 3. Assert Redis key exists and has remaining TTL
    cached_bytes = await redis_client.get(redis_key)
    assert cached_bytes is not None, "Redis cache key was not populated on cache miss!"
    ttl = await redis_client.ttl(redis_key)
    assert 0 < ttl <= settings.USER_CACHE_TTL_SECONDS

    # 4. Call /auth/me a second time -> Served from Redis cache hit
    resp2 = await client.get("/auth/me", headers=alice_headers)
    assert resp2.status_code == 200
    assert resp2.json()["email"] == "alice@orga.com"

    # 5. Invalidate cache -> verify key is purged
    await invalidate_user_cache(ALICE_USER_ID)
    cached_after = await redis_client.get(redis_key)
    assert cached_after is None, "Redis key was not purged by invalidate_user_cache!"
