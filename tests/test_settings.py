import pytest
from pydantic import ValidationError

from app.config import DEFAULT_DATABASE_URL, DatabaseSettings, Settings


def test_settings_parses_required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:telegram")
    monkeypatch.setenv("WAVESPEED_API_KEY", "wavespeed-key")
    monkeypatch.setenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./data/app.db",
    )
    monkeypatch.setenv("ADMIN_IDS", "123456789,987654321")
    monkeypatch.setenv("SUPPORT_CHAT_ID", "-1001234567890")

    settings = Settings(_env_file=None)

    assert settings.bot_token.get_secret_value() == "123:telegram"
    assert settings.wavespeed_api_key.get_secret_value() == "wavespeed-key"
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.admin_ids == [123456789, 987654321]
    assert settings.support_chat_id == -1001234567890
    assert settings.default_image_size == "2048*2048"
    assert settings.wavespeed_edit_model_path == "bytedance/seedream-v4/edit"


def test_database_settings_reads_database_url_without_bot_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./custom/app.db",
    )

    settings = DatabaseSettings(_env_file=None)

    assert settings.database_url == "sqlite+aiosqlite:///./custom/app.db"


def test_database_settings_uses_postgresql_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://USER:PASSWORD@db.example.com:5432/DB_NAME?ssl=require",
    )

    settings = DatabaseSettings(_env_file=None)

    assert settings.database_url == (
        "postgresql+asyncpg://USER:PASSWORD@db.example.com:5432/DB_NAME?ssl=require"
    )


@pytest.mark.parametrize("database_url", [None, ""])
def test_database_settings_uses_sqlite_default_without_database_url(
    database_url: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    if database_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", database_url)

    settings = DatabaseSettings(_env_file=None)

    assert settings.database_url == DEFAULT_DATABASE_URL


def test_settings_uses_sqlite_default_for_missing_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:telegram")
    monkeypatch.setenv("WAVESPEED_API_KEY", "wavespeed-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == DEFAULT_DATABASE_URL


def test_settings_rejects_invalid_default_image_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:telegram")
    monkeypatch.setenv("WAVESPEED_API_KEY", "wavespeed-key")
    monkeypatch.setenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./data/app.db",
    )
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
        "sqlite+aiosqlite:///./data/app.db",
    )
    monkeypatch.setenv("TELEGRAM_PROXY", "")
    monkeypatch.setenv("ADMIN_IDS", "123456789")
    monkeypatch.delenv("SUPPORT_CHAT_ID", raising=False)

    settings = Settings(_env_file=None)

    assert settings.support_chat_id is None
    assert settings.telegram_proxy is None
