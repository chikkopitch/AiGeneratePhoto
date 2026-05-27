from dataclasses import dataclass
from pathlib import Path
import socket

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import (
    DATABASE_CONNECTION_ERROR_MESSAGE,
    check_database_connection,
    create_database_engine,
    create_session_factory,
    initialize_database,
)


@dataclass
class DummySettings:
    database_url: str


def sqlite_file_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


@pytest.mark.asyncio
async def test_create_database_engine_uses_settings_database_url() -> None:
    engine = create_database_engine(DummySettings("sqlite+aiosqlite:///:memory:"))

    try:
        assert engine.echo is False
        assert engine.url.drivername == "sqlite+aiosqlite"
        assert engine.url.database == ":memory:"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_database_engine_falls_back_to_sqlite_for_postgresql_url() -> None:
    engine = create_database_engine(
        DummySettings("postgresql+asyncpg://user:pass@db.example.com:5432/db?ssl=require")
    )

    try:
        assert engine.url.drivername == "sqlite+aiosqlite"
        assert engine.url.database == "./data/app.db"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_database_engine_creates_sqlite_parent_directory(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "app.db"
    engine = create_database_engine(sqlite_file_url(database_path))

    try:
        assert database_path.parent.is_dir()
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
async def test_initialize_database_creates_sqlite_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "app.db"
    engine = create_database_engine(sqlite_file_url(database_path))

    try:
        await initialize_database(engine)

        async with engine.begin() as connection:
            result = await connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            )
            table_names = set(result.scalars().all())

        assert {"users", "generations"}.issubset(table_names)
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


@dataclass
class DummyUrl:
    host: str


class FailingEngine:
    url = DummyUrl(host="db.example.com")

    def begin(self) -> FailingConnectionContext:
        return FailingConnectionContext()


@pytest.mark.asyncio
async def test_check_database_connection_raises_clear_error_on_failure() -> None:
    with pytest.raises(RuntimeError, match=DATABASE_CONNECTION_ERROR_MESSAGE):
        await check_database_connection(FailingEngine())  # type: ignore[arg-type]


class DnsFailingConnectionContext:
    async def __aenter__(self) -> None:
        raise socket.gaierror(-2, "Name or service not known")

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        return False


class DnsFailingEngine:
    url = DummyUrl(host="bad-host.example")

    def begin(self) -> DnsFailingConnectionContext:
        return DnsFailingConnectionContext()


@pytest.mark.asyncio
async def test_check_database_connection_reports_unresolved_host() -> None:
    with pytest.raises(RuntimeError, match="bad-host.example"):
        await check_database_connection(DnsFailingEngine())  # type: ignore[arg-type]
