"""
Health Probe Tests (CONTRACTS.md Section 3.C).
Verifies liveness and readiness endpoints.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_probe(client: AsyncClient) -> None:
    """Liveness probe must return 200 OK without touching external dependencies."""
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "alive"}


@pytest.mark.asyncio
async def test_readiness_probe(client: AsyncClient) -> None:
    """Readiness probe must verify live PostgreSQL and Redis connections."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ready"}
