import pytest

from app.config.database_url import DATABASE_URL_NOT_SET_MESSAGE, normalize_database_url


def test_normalize_database_url_replaces_postgresql_scheme_and_sslmode() -> None:
    url = "postgresql://user:pass@host:5432/db?sslmode=require"

    assert normalize_database_url(url) == (
        "postgresql+asyncpg://user:pass@host:5432/db?ssl=require"
    )


def test_normalize_database_url_keeps_asyncpg_scheme_and_ssl() -> None:
    url = "postgresql+asyncpg://user:pass@host:5432/db?ssl=require"

    assert normalize_database_url(url) == url


def test_normalize_database_url_preserves_other_query_params() -> None:
    url = (
        "postgresql://user:pass@host:5432/db?"
        "connect_timeout=10&sslmode=require&application_name=photo_bot"
    )

    assert normalize_database_url(url) == (
        "postgresql+asyncpg://user:pass@host:5432/db?"
        "connect_timeout=10&ssl=require&application_name=photo_bot"
    )


def test_normalize_database_url_does_not_change_credentials_host_port_or_database() -> None:
    url = "postgresql://user:pa%3Ass@db.example.com:6543/photo_bot?sslmode=require"

    assert normalize_database_url(url) == (
        "postgresql+asyncpg://user:pa%3Ass@db.example.com:6543/photo_bot?ssl=require"
    )


def test_normalize_database_url_rejects_empty_url() -> None:
    with pytest.raises(ValueError, match=DATABASE_URL_NOT_SET_MESSAGE):
        normalize_database_url("")
