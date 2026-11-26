"""
Shared Pytest Fixtures for FastAPI Microservice Integration Tests.
Provides async HTTP clients and deterministic persona auth headers.
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import async_session_factory
from app.core.redis import get_redis_client
from app.core.security import create_access_token
from app.main import create_app

# Deterministic User & Org UUIDs matching locked CONTRACTS.md Section 1
ORG_A_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ORG_B_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

ALICE_USER_ID = uuid.UUID("aaaaaaa1-1111-1111-1111-111111111111")    # Org A Admin
BOB_USER_ID = uuid.UUID("bbbbbbb1-1111-1111-1111-111111111111")      # Org A Support Agent
CHARLIE_USER_ID = uuid.UUID("ccccccc1-1111-1111-1111-111111111111")  # Org A Customer
DAVE_USER_ID = uuid.UUID("ddddddd2-2222-2222-2222-222222222222")     # Org B Admin
EVE_USER_ID = uuid.UUID("eeeeeee1-1111-1111-1111-111111111111")      # Org B Customer


@pytest.fixture(scope="session")
def app_instance():
    """Create a singleton FastAPI application instance for test sessions."""
    return create_app()


@pytest.fixture(scope="session", autouse=True)
async def clean_redis_cache():
    """Wipe Redis cache before and after test suite to prevent stale session interference."""
    client = get_redis_client()
    try:
        await client.flushdb()
    except Exception:
        pass
    yield
    try:
        await client.flushdb()
    except Exception:
        pass


@pytest.fixture(scope="session")
async def client(app_instance) -> AsyncGenerator[AsyncClient, None]:
    """Provides an isolated async HTTP client bound to the FastAPI ASGI application."""
    async with AsyncClient(
        transport=ASGITransport(app=app_instance),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def db_session():
    """Provides an isolated async database session for assertions against PostgreSQL."""
    async with async_session_factory() as session:
        yield session


def _mint_headers(user_id: uuid.UUID) -> dict[str, str]:
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def alice_headers() -> dict[str, str]:
    """Org A Admin headers (Alice - * wildcard permission)."""
    return _mint_headers(ALICE_USER_ID)


@pytest.fixture
def bob_headers() -> dict[str, str]:
    """Org A Support Agent headers (Bob - tickets, internal notes, staff KB)."""
    return _mint_headers(BOB_USER_ID)


@pytest.fixture
def charlie_headers() -> dict[str, str]:
    """Org A Customer headers (Charlie - own tickets and public KB only)."""
    return _mint_headers(CHARLIE_USER_ID)


@pytest.fixture
def dave_headers() -> dict[str, str]:
    """Org B Admin headers (Dave - * wildcard permission in Org B)."""
    return _mint_headers(DAVE_USER_ID)


@pytest.fixture
def eve_headers() -> dict[str, str]:
    """Org B Customer headers (Eve - own tickets and public KB only in Org B)."""
    return _mint_headers(EVE_USER_ID)
