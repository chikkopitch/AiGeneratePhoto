import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_parses_required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:telegram")
    monkeypatch.setenv("WAVESPEED_API_KEY", "wavespeed-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/photo_bot")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("TELEGRAM_PROXY", "socks5://213.159.196.77:1080")
    monkeypatch.setenv("ADMIN_IDS", "123456789,987654321")
    monkeypatch.setenv("SUPPORT_CHAT_ID", "-1001234567890")

    settings = Settings(_env_file=None)

    assert settings.bot_token.get_secret_value() == "123:telegram"
    assert settings.wavespeed_api_key.get_secret_value() == "wavespeed-key"
    assert settings.database_url == "postgresql+asyncpg://postgres:postgres@postgres:5432/photo_bot"
    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.telegram_proxy == "socks5://213.159.196.77:1080"
    assert settings.admin_ids == [123456789, 987654321]
    assert settings.support_chat_id == -1001234567890
    assert settings.default_image_size == "2048*2048"


def test_settings_rejects_invalid_default_image_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:telegram")
    monkeypatch.setenv("WAVESPEED_API_KEY", "wavespeed-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/photo_bot")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.delenv("TELEGRAM_PROXY", raising=False)
    monkeypatch.setenv("ADMIN_IDS", "123456789")
    monkeypatch.setenv("SUPPORT_CHAT_ID", "-1001234567890")
    monkeypatch.setenv("DEFAULT_IMAGE_SIZE", "2048x2048")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_allows_missing_support_chat_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:telegram")
    monkeypatch.setenv("WAVESPEED_API_KEY", "wavespeed-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/photo_bot")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("TELEGRAM_PROXY", "")
    monkeypatch.setenv("ADMIN_IDS", "123456789")
    monkeypatch.delenv("SUPPORT_CHAT_ID", raising=False)

    settings = Settings(_env_file=None)

    assert settings.support_chat_id is None
    assert settings.telegram_proxy is None
