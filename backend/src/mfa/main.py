from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.api.router import router as api_router
from mfa.config import get_settings
from mfa.core.errors import MFAError, mfa_error_handler
from mfa.core.logging import configure_logging
from mfa.db.session import async_session_factory

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger = structlog.get_logger(__name__)
    if settings.auth_strict and not settings.cognito_user_pool_id:
        logger.warning(
            "auth_strict_without_cognito",
            hint="Set COGNITO_USER_POOL_ID + COGNITO_APP_CLIENT_ID for JWT validation",
        )
    logger.info(
        "app_starting",
        env=settings.env,
        auth_strict=settings.auth_strict,
        cognito_enabled=bool(settings.cognito_user_pool_id),
    )
    yield
    logger.info("app_stopping")


def create_app() -> FastAPI:
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        lifespan=lifespan,
    )
    app.add_exception_handler(MFAError, mfa_error_handler)
    app.include_router(api_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    @app.get("/health/db", tags=["health"])
    async def health_db() -> dict[str, str]:
        async with async_session_factory() as session:
            await _check_db(session)
        return {"status": "ok", "database": "connected"}

    return app


async def _check_db(session: AsyncSession) -> None:
    await session.execute(text("SELECT 1"))


app = create_app()
