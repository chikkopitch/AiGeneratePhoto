from dataclasses import dataclass

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import (
    DATABASE_CONNECTION_ERROR_MESSAGE,
    check_database_connection,
    create_database_engine,
    create_session_factory,
)


@dataclass
class DummySettings:
    database_url: str


@pytest.mark.asyncio
async def test_create_database_engine_uses_settings_and_normalizes_database_url() -> None:
    engine = create_database_engine(
        DummySettings(
            "postgresql://user:pass@host:5432/db?"
            "connect_timeout=10&sslmode=require"
        )
    )

    try:
        assert engine.echo is False
        assert engine.url.drivername == "postgresql+asyncpg"
        assert engine.url.username == "user"
        assert engine.url.password == "pass"
        assert engine.url.host == "host"
        assert engine.url.port == 5432
        assert engine.url.database == "db"
        assert engine.url.query["connect_timeout"] == "10"
        assert engine.url.query["ssl"] == "require"
        assert "sslmode" not in engine.url.query
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_session_factory_builds_async_sessions() -> None:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            assert isinstance(session, AsyncSession)
            assert session.sync_session.expire_on_commit is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_check_database_connection_executes_select_one() -> None:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")

    try:
        await check_database_connection(engine)
    finally:
        await engine.dispose()


class FailingConnectionContext:
    async def __aenter__(self) -> None:
        raise OSError("connection refused")

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        return False


class FailingEngine:
    def begin(self) -> FailingConnectionContext:
        return FailingConnectionContext()


@pytest.mark.asyncio
async def test_check_database_connection_raises_clear_error_on_failure() -> None:
    with pytest.raises(RuntimeError, match=DATABASE_CONNECTION_ERROR_MESSAGE):
        await check_database_connection(FailingEngine())  # type: ignore[arg-type]
