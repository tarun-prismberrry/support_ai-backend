"""
FastAPI Application Entrypoint & Factory.
Configures lifespan hooks, CORS middleware, and standardized contract error envelopes.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.database import engine
from app.core.redis import close_redis_pool
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.invoices import router as invoices_router
from app.api.v1.notes import router as notes_router
from app.api.v1.tickets import router as tickets_router

settings = get_settings()

# Canonical HTTP status -> CONTRACTS.md error code mapping
STATUS_TO_ERROR_CODE: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "VALIDATION_ERROR",
    status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and graceful shutdown of shared infrastructure pools."""
    yield
    await engine.dispose()
    await close_redis_pool()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    application = FastAPI(
        title="Agentic Support Backend",
        description="Multi-Tenant B2B Customer Support AI Backend & Database Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Enable CORS for local frontend and microservice testing
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.ENVIRONMENT == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        code = STATUS_TO_ERROR_CODE.get(exc.status_code, "INTERNAL_ERROR")
        message = str(exc.detail)
        details = None
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", code)
            message = exc.detail.get("message", message)
            details = exc.detail.get("details", None)
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "details": details,
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                }
            },
        )
    # Mount routers at both root and /api/v1 prefix for backwards compatibility and API versioning
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(health_router)
    api_v1.include_router(auth_router)
    api_v1.include_router(tickets_router)
    api_v1.include_router(notes_router)
    api_v1.include_router(invoices_router)
    application.include_router(api_v1)

    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(tickets_router)
    application.include_router(notes_router)
    application.include_router(invoices_router)
    return application


app = create_app()
