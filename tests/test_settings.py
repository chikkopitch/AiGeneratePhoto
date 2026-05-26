import pytest
from pydantic import ValidationError

from app.config import DATABASE_URL_NOT_SET_MESSAGE, DatabaseSettings, Settings


def test_settings_parses_required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:telegram")
    monkeypatch.setenv("WAVESPEED_API_KEY", "wavespeed-key")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://USER:PASSWORD@HOST:5432/DB_NAME?sslmode=require",
    )
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("ADMIN_IDS", "123456789,987654321")
    monkeypatch.setenv("SUPPORT_CHAT_ID", "-1001234567890")

    settings = Settings(_env_file=None)

    assert settings.bot_token.get_secret_value() == "123:telegram"
    assert settings.wavespeed_api_key.get_secret_value() == "wavespeed-key"
    assert settings.database_url == "postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB_NAME?ssl=require"
    assert settings.redis_url is None
    assert settings.admin_ids == [123456789, 987654321]
    assert settings.support_chat_id == -1001234567890
    assert settings.default_image_size == "2048*2048"


def test_database_settings_reads_database_url_without_bot_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://USER:PASSWORD@HOST:5432/DB_NAME?sslmode=require",
    )

    settings = DatabaseSettings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB_NAME?ssl=require"


def test_settings_parses_optional_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:telegram")
    monkeypatch.setenv("WAVESPEED_API_KEY", "wavespeed-key")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB_NAME?ssl=require",
    )
    monkeypatch.setenv("REDIS_URL", "redis://cache.example.com:6379/0")

    settings = Settings(_env_file=None)

    assert settings.redis_url == "redis://cache.example.com:6379/0"


def test_settings_rejects_missing_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:telegram")
    monkeypatch.setenv("WAVESPEED_API_KEY", "wavespeed-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert DATABASE_URL_NOT_SET_MESSAGE in str(exc_info.value)


def test_settings_rejects_invalid_default_image_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:telegram")
    monkeypatch.setenv("WAVESPEED_API_KEY", "wavespeed-key")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB_NAME?ssl=require",
    )
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_PROXY", raising=False)
    monkeypatch.setenv("ADMIN_IDS", "123456789")
    monkeypatch.setenv("SUPPORT_CHAT_ID", "-1001234567890")
    monkeypatch.setenv("DEFAULT_IMAGE_SIZE", "2048x2048")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_allows_missing_support_chat_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:telegram")
    monkeypatch.setenv("WAVESPEED_API_KEY", "wavespeed-key")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB_NAME?ssl=require",
    )
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("TELEGRAM_PROXY", "")
    monkeypatch.setenv("ADMIN_IDS", "123456789")
    monkeypatch.delenv("SUPPORT_CHAT_ID", raising=False)

    settings = Settings(_env_file=None)

    assert settings.support_chat_id is None
    assert settings.telegram_proxy is None
    assert settings.redis_url is None
