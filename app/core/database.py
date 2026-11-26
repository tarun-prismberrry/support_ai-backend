"""
Database Engine, Async Session Factory, Base Model, and RLS Context.
Built with SQLAlchemy 2.0 and asyncpg for non-blocking PostgreSQL queries.
"""

from collections.abc import AsyncGenerator
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# 1. Asynchronous SQLAlchemy Engine
# Uses asyncpg driver with connection pool sizing from settings
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Automatically recycles dropped connections
)

# 2. Async Session Factory
# expire_on_commit=False is crucial for async SQLAlchemy to prevent MissingGreenlet errors
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# 3. Declarative Base Model for all ORM entities
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.0 models."""
    pass


# 4. FastAPI Dependency: Yields an isolated AsyncSession per request
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an asynchronous database session.
    Automatically handles commit/rollback and ensures the connection is closed.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# 5. Multi-Tenant Row-Level Security (RLS) Session Setter
async def set_db_tenant_context(session: AsyncSession, org_id: UUID | str) -> None:
    """
    Sets the transaction-local 'app.current_org_id' configuration variable in PostgreSQL.
    
    The third parameter 'true' makes this setting local to the current transaction
    (equivalent to SET LOCAL). This guarantees tenant isolation in connection pools.
    """
    await session.execute(
        text("SELECT set_config('app.current_org_id', :org_id, true)"),
        {"org_id": str(org_id)},
    )