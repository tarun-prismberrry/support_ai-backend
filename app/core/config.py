"""
Application Configuration and Environment Settings.
Validated at startup using Pydantic Settings (PEP 621 / Pydantic v2).
"""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Mode
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # PostgreSQL Connection Strings
    # Async driver for FastAPI queries (asyncpg)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/support_ai_db"
    # Sync driver for Alembic database migrations
    DATABASE_URL_SYNC: str = "postgresql+psycopg://postgres:postgres@localhost:5432/support_ai_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # JWT Authentication & Cryptographic Parameters
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_ISSUER: str = "support-ai-backend"
    JWT_AUDIENCE: str = "support-ai-services"

    # Pydantic v2 Settings Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra environment variables not defined here
    )


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached singleton instance of application settings.
    Ensures .env is read once during application startup.
    """
    return Settings()