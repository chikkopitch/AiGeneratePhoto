from datetime import UTC, datetime, timedelta

from app.services.key_value_store import KeyValueStore

GENERATION_ACTIVE_MESSAGE = "У вас уже идёт генерация. Дождитесь результата."
GENERATION_DAILY_LIMIT_MESSAGE = "Вы использовали дневной лимит генераций."
GENERATION_COOLDOWN_MESSAGE = "Пожалуйста, подождите немного перед следующей генерацией."
SUPPORT_COOLDOWN_MESSAGE = "Пожалуйста, подождите немного перед следующим обращением в поддержку."


class RateLimitService:
    def __init__(
        self,
        redis: KeyValueStore,
        daily_generation_limit: int = 5,
        generation_cooldown_seconds: int = 30,
        support_cooldown_seconds: int = 60,
        active_generation_ttl_seconds: int = 30 * 60,
    ) -> None:
        self._redis = redis
        self._daily_generation_limit = daily_generation_limit
        self._generation_cooldown_seconds = generation_cooldown_seconds
        self._support_cooldown_seconds = support_cooldown_seconds
        self._active_generation_ttl_seconds = active_generation_ttl_seconds

    async def can_generate(self, user_id: int) -> tuple[bool, str | None]:
        if await self._redis.exists(self._generation_active_key(user_id)):
            return False, GENERATION_ACTIVE_MESSAGE

        daily_count = await self._redis.get(self._generation_daily_key(user_id))
        if daily_count is not None and int(daily_count) >= self._daily_generation_limit:
            return False, GENERATION_DAILY_LIMIT_MESSAGE

        if await self._redis.exists(self._generation_cooldown_key(user_id)):
            return False, GENERATION_COOLDOWN_MESSAGE

        return True, None

    async def mark_generation_started(self, user_id: int) -> None:
        await self._redis.setex(
            self._generation_active_key(user_id),
            self._active_generation_ttl_seconds,
            "1",
        )
        await self._redis.setex(
            self._generation_cooldown_key(user_id),
            self._generation_cooldown_seconds,
            "1",
        )

        daily_key = self._generation_daily_key(user_id)
        daily_count = await self._redis.incr(daily_key)
        if daily_count == 1:
            await self._redis.expire(daily_key, self._seconds_until_next_utc_day())

    async def mark_generation_finished(self, user_id: int) -> None:
        await self._redis.delete(self._generation_active_key(user_id))

    async def can_contact_support(self, user_id: int) -> tuple[bool, str | None]:
        if await self._redis.exists(self._support_cooldown_key(user_id)):
            return False, SUPPORT_COOLDOWN_MESSAGE
        return True, None

    async def mark_support_contact(self, user_id: int) -> None:
        await self._redis.setex(
            self._support_cooldown_key(user_id),
            self._support_cooldown_seconds,
            "1",
        )

    @staticmethod
    def _generation_active_key(user_id: int) -> str:
        return f"rate:generation:active:{user_id}"

    @staticmethod
    def _generation_cooldown_key(user_id: int) -> str:
        return f"rate:generation:cooldown:{user_id}"

    @staticmethod
    def _generation_daily_key(user_id: int) -> str:
        return f"rate:generation:daily:{datetime.now(UTC).date().isoformat()}:{user_id}"

    @staticmethod
    def _support_cooldown_key(user_id: int) -> str:
        return f"rate:support:cooldown:{user_id}"

    @staticmethod
    def _seconds_until_next_utc_day() -> int:
        now = datetime.now(UTC)
        tomorrow = (now + timedelta(days=1)).date()
        next_day = datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC)
        return max(1, int((next_day - now).total_seconds()))
