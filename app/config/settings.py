import re
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.config.database_url import DEFAULT_DATABASE_URL, validate_external_database_url


class DatabaseSettings(BaseSettings):
    database_url: str = Field(default=DEFAULT_DATABASE_URL, validate_default=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: object) -> str:
        return validate_external_database_url(None if value is None else str(value))


class Settings(DatabaseSettings):
    bot_token: SecretStr
    wavespeed_api_key: SecretStr

    telegram_proxy: str | None = None
    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    support_chat_id: int | None = None
    default_image_size: str = "2048*2048"

    wavespeed_base_url: str = "https://api.wavespeed.ai"
    wavespeed_model_path: str = "bytedance/seedream-v4"
    wavespeed_edit_model_path: str = "bytedance/seedream-v4/edit"
    wavespeed_poll_interval_seconds: float = 2.0
    wavespeed_poll_attempts: int = 60
    wavespeed_request_timeout_seconds: float = 60.0

    log_level: str = "INFO"

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [int(item) for item in value]
        raise ValueError("ADMIN_IDS must be a comma-separated list of Telegram user ids")

    @field_validator("support_chat_id", mode="before")
    @classmethod
    def parse_support_chat_id(cls, value: object) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    @field_validator("telegram_proxy", mode="before")
    @classmethod
    def parse_telegram_proxy(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        return str(value)

    @field_validator("default_image_size")
    @classmethod
    def validate_default_image_size(cls, value: str) -> str:
        if not re.fullmatch(r"\d+\*\d+", value):
            raise ValueError("Use WIDTH*HEIGHT format, for example 2048*2048")
        return value

    @field_validator("wavespeed_poll_attempts")
    @classmethod
    def validate_poll_attempts(cls, value: int) -> int:
        if value < 1:
            raise ValueError("wavespeed_poll_attempts must be greater than 0")
        return value

    @field_validator("wavespeed_poll_interval_seconds")
    @classmethod
    def validate_poll_interval(cls, value: float) -> float:
        if value < 0:
            raise ValueError("wavespeed_poll_interval_seconds cannot be negative")
        return value
