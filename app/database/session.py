import logging
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import normalize_database_url

logger = logging.getLogger(__name__)

DATABASE_CONNECTION_ERROR_MESSAGE = (
    "Database is unavailable. Please check DATABASE_URL and external PostgreSQL connection."
)

_engine: AsyncEngine | None = None


class DatabaseSettings(Protocol):
    database_url: str


def create_database_engine(settings: DatabaseSettings | str) -> AsyncEngine:
    global _engine

    raw_database_url = settings if isinstance(settings, str) else settings.database_url
    database_url = normalize_database_url(raw_database_url)
    _engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
    )
    return _engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def check_database_connection(engine: AsyncEngine | None = None) -> None:
    database_engine = engine or _engine
    if database_engine is None:
        raise RuntimeError("Database engine is not initialized. Call create_database_engine first.")

    try:
        async with database_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception(
            "Database connection check failed",
            extra={
                "status": "database_unavailable",
                "error_type": type(exc).__name__,
            },
        )
        raise RuntimeError(DATABASE_CONNECTION_ERROR_MESSAGE) from exc
