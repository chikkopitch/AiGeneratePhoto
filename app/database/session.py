import logging
from pathlib import Path
import socket
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config.database_url import normalize_database_url
from app.database.base import Base
from app.database.models import Generation, User  # noqa: F401

logger = logging.getLogger(__name__)

DATABASE_CONNECTION_ERROR_MESSAGE = (
    "Database is unavailable. Please check DATABASE_URL and database file permissions."
)
SQLITE_INITIALIZATION_ERROR_MESSAGE = (
    "SQLite database cannot be initialized. Please check the data directory permissions."
)

_engine: AsyncEngine | None = None


class DatabaseSettings(Protocol):
    database_url: str


def create_database_engine(settings: DatabaseSettings | str) -> AsyncEngine:
    global _engine

    raw_database_url = settings if isinstance(settings, str) else settings.database_url
    database_url = normalize_database_url(raw_database_url)
    _ensure_sqlite_database_directory(database_url)
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


async def initialize_database(engine: AsyncEngine | None = None) -> None:
    database_engine = engine or _engine
    if database_engine is None:
        raise RuntimeError("Database engine is not initialized. Call create_database_engine first.")
    if not _is_sqlite_url(database_engine.url):
        return

    try:
        async with database_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        logger.error(
            "SQLite database initialization failed",
            extra={
                "status": "database_initialization_failed",
                "database_path": database_engine.url.database or "-",
                "error_type": type(exc).__name__,
            },
        )
        raise RuntimeError(SQLITE_INITIALIZATION_ERROR_MESSAGE) from exc


async def check_database_connection(engine: AsyncEngine | None = None) -> None:
    database_engine = engine or _engine
    if database_engine is None:
        raise RuntimeError("Database engine is not initialized. Call create_database_engine first.")

    try:
        async with database_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        host = database_engine.url.host or "-"
        logger.error(
            "Database connection check failed",
            extra={
                "status": "database_unavailable",
                "database_host": host,
                "error_type": type(exc).__name__,
            },
        )
        raise RuntimeError(_build_database_connection_error_message(exc, host)) from exc


def _build_database_connection_error_message(exc: Exception, host: str) -> str:
    if _has_cause(exc, socket.gaierror):
        return (
            f"Database host '{host}' cannot be resolved. "
            "Check DATABASE_URL on the server."
        )
    return DATABASE_CONNECTION_ERROR_MESSAGE


def _ensure_sqlite_database_directory(database_url: str) -> None:
    url = make_url(database_url)
    if not _is_sqlite_url(url) or not url.database or url.database == ":memory:":
        return

    database_path = Path(url.database)
    if not database_path.is_absolute():
        database_path = Path.cwd() / database_path
    database_path.parent.mkdir(parents=True, exist_ok=True)


def _is_sqlite_url(url: URL) -> bool:
    return url.get_backend_name() == "sqlite"


def _has_cause(exc: BaseException, expected_type: type[BaseException]) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, expected_type):
            return True
        current = current.__cause__ or current.__context__
    return False
