import logging
from dataclasses import dataclass

import pytest
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from app.main import create_storage


@dataclass
class DummySettings:
    redis_url: str | None


@pytest.mark.parametrize("redis_url", ["", None])
def test_create_storage_uses_memory_storage_for_empty_redis_url(
    redis_url: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        storage = create_storage(DummySettings(redis_url=redis_url))  # type: ignore[arg-type]

    assert isinstance(storage, MemoryStorage)
    assert "Using MemoryStorage for FSM" in caplog.text


@pytest.mark.asyncio
async def test_create_storage_uses_redis_storage_for_configured_redis_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        storage = create_storage(  # type: ignore[arg-type]
            DummySettings(redis_url="redis://cache.example.com:6379/0")
        )

    try:
        assert isinstance(storage, RedisStorage)
        assert storage.redis.connection_pool.connection_kwargs["host"] == "cache.example.com"
        assert "Using RedisStorage for FSM" in caplog.text
    finally:
        await storage.close()
