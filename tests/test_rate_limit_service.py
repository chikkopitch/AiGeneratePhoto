import pytest

from app.services.rate_limit import (
    GENERATION_ACTIVE_MESSAGE,
    GENERATION_COOLDOWN_MESSAGE,
    GENERATION_DAILY_LIMIT_MESSAGE,
    SUPPORT_COOLDOWN_MESSAGE,
    RateLimitService,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}

    async def exists(self, key: str) -> int:
        return 1 if key in self.values else 0

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def setex(self, key: str, seconds: int, value: str) -> None:
        self.values[key] = value
        self.expirations[key] = seconds

    async def incr(self, key: str) -> int:
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value

    async def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


@pytest.mark.asyncio
async def test_generation_active_limit_until_finished() -> None:
    redis = FakeRedis()
    service = RateLimitService(redis)  # type: ignore[arg-type]

    await service.mark_generation_started(1)

    assert await service.can_generate(1) == (False, GENERATION_ACTIVE_MESSAGE)

    await service.mark_generation_finished(1)

    assert await service.can_generate(1) == (False, GENERATION_COOLDOWN_MESSAGE)


@pytest.mark.asyncio
async def test_generation_daily_limit() -> None:
    redis = FakeRedis()
    service = RateLimitService(  # type: ignore[arg-type]
        redis,
        daily_generation_limit=1,
        generation_cooldown_seconds=0,
    )

    await service.mark_generation_started(1)
    await service.mark_generation_finished(1)
    redis.values.pop(service._generation_cooldown_key(1), None)

    assert await service.can_generate(1) == (False, GENERATION_DAILY_LIMIT_MESSAGE)


@pytest.mark.asyncio
async def test_support_cooldown_limit() -> None:
    redis = FakeRedis()
    service = RateLimitService(redis)  # type: ignore[arg-type]

    assert await service.can_contact_support(1) == (True, None)

    await service.mark_support_contact(1)

    assert await service.can_contact_support(1) == (False, SUPPORT_COOLDOWN_MESSAGE)
