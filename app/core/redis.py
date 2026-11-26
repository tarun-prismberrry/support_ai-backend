"""
Redis connection pooling & client factory.
Provides a shared asynchronous connection pool across the application lifecycle.
"""

from __future__ import annotations

import redis.asyncio as aioredis
from app.core.config import get_settings

settings = get_settings()

# Shared asynchronous Redis connection pool (up to 20 concurrent connections)
redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=20,
    decode_responses=False,
)


def get_redis_client() -> aioredis.Redis:
    """
    Returns an async Redis client backed by the shared connection pool.
    Connections are returned to the pool rather than closed/re-opened.
    """
    return aioredis.Redis(connection_pool=redis_pool)


async def close_redis_pool() -> None:
    """Closes all connections in the pool gracefully during shutdown."""
    await redis_pool.disconnect()
