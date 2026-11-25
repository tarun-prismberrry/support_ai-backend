"""
Health Check Probes (Liveness & Readiness).
Implements CONTRACTS.md Section 3.C for container orchestration and uptime checks.
"""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db

router = APIRouter(prefix="/health", tags=["Health"])
settings = get_settings()


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_probe() -> dict[str, str]:
    """Process liveness check. Never queries external dependencies."""
    return {"status": "alive"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_probe(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Dependency readiness check verifying PostgreSQL pool and Redis connectivity."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {exc}",
        ) from exc

    redis_client = aioredis.from_url(settings.REDIS_URL)
    try:
        pong = await redis_client.ping()
        if not pong:
            raise RuntimeError("Redis ping returned falsy response")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis unavailable: {exc}",
        ) from exc
    finally:
        await redis_client.aclose()

    return {"status": "ready"}