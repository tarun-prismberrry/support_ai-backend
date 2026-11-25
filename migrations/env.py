import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# -------------------------------------------------------------------------
# 1. Application Settings & Relational Metadata Discovery
# -------------------------------------------------------------------------
from app.core.config import get_settings
from app.core.database import Base
import app.models  # Ensures all 10 models register with Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# -------------------------------------------------------------------------
# 2. Dynamically Inject Database Connection URL (12-Factor App)
# -------------------------------------------------------------------------
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# -------------------------------------------------------------------------
# 3. Bind Declarative Base Metadata for Autogenerate Support
# -------------------------------------------------------------------------
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL DDL scripts)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=False,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations within an active database connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create async engine and run migrations with asyncpg."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()