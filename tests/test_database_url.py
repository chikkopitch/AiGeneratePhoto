import pytest

from app.config.database_url import (
    DEFAULT_DATABASE_URL,
    DATABASE_URL_EXTERNAL_HOST_MESSAGE,
    normalize_database_url,
    validate_external_database_url,
)


def test_normalize_database_url_replaces_postgresql_scheme_and_sslmode() -> None:
    url = "postgresql://user:pass@db.example.com:5432/db?sslmode=require"

    assert normalize_database_url(url) == (
        "postgresql+asyncpg://user:pass@db.example.com:5432/db?ssl=require"
    )


def test_normalize_database_url_keeps_asyncpg_scheme_and_ssl() -> None:
    url = "postgresql+asyncpg://user:pass@db.example.com:5432/db?ssl=require"

    assert normalize_database_url(url) == url


def test_normalize_database_url_preserves_other_query_params() -> None:
    url = (
        "postgresql://user:pass@db.example.com:5432/db?"
        "connect_timeout=10&sslmode=require&application_name=photo_bot"
    )

    assert normalize_database_url(url) == (
        "postgresql+asyncpg://user:pass@db.example.com:5432/db?"
        "connect_timeout=10&ssl=require&application_name=photo_bot"
    )


def test_normalize_database_url_does_not_change_credentials_host_port_or_database() -> None:
    url = "postgresql://user:pa%3Ass@db.example.com:6543/photo_bot?sslmode=require"

    assert normalize_database_url(url) == (
        "postgresql+asyncpg://user:pa%3Ass@db.example.com:6543/photo_bot?ssl=require"
    )


@pytest.mark.parametrize("url", [None, "", "   "])
def test_normalize_database_url_uses_sqlite_default_for_empty_url(url: str | None) -> None:
    assert normalize_database_url(url) == DEFAULT_DATABASE_URL


def test_normalize_database_url_keeps_sqlite_url() -> None:
    url = "sqlite+aiosqlite:///./data/app.db"

    assert normalize_database_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "DATABASE_URL=sqlite+aiosqlite:///./data/app.db",
        "DATABASE_URL=DATABASE_URL=sqlite+aiosqlite:///./data/app.db",
        "database_url=sqlite+aiosqlite:///./data/app.db",
    ],
)
def test_normalize_database_url_strips_accidental_env_assignment_prefix(url: str) -> None:
    assert normalize_database_url(url) == "sqlite+aiosqlite:///./data/app.db"


def test_normalize_database_url_removes_asyncpg_unsupported_channel_binding() -> None:
    url = (
        "postgresql://user:pass@db.example.com/db?"
        "sslmode=require&channel_binding=require"
    )

    assert normalize_database_url(url) == (
        "postgresql+asyncpg://user:pass@db.example.com/db?ssl=require"
    )


@pytest.mark.parametrize("host", ["HOST", "host", "db", "postgres", "localhost", "127.0.0.1"])
def test_validate_external_database_url_rejects_local_or_placeholder_hosts(host: str) -> None:
    url = f"postgresql://user:pass@{host}:5432/db?sslmode=require"

    with pytest.raises(ValueError, match=DATABASE_URL_EXTERNAL_HOST_MESSAGE):
        validate_external_database_url(url)


def test_validate_external_database_url_allows_external_postgresql_host() -> None:
    url = "postgresql://user:pass@node1.pghost.ru:15727/photo_bot"

    assert validate_external_database_url(url) == (
        "postgresql+asyncpg://user:pass@node1.pghost.ru:15727/photo_bot"
    )
