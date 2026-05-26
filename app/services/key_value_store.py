from time import monotonic
from typing import Protocol


class KeyValueStore(Protocol):
    async def exists(self, key: str) -> int:
        ...

    async def get(self, key: str) -> str | bytes | None:
        ...

    async def set(self, key: str, value: str) -> bool:
        ...

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        ...

    async def incr(self, key: str) -> int:
        ...

    async def expire(self, key: str, seconds: int) -> bool:
        ...

    async def delete(self, key: str) -> int:
        ...


class InMemoryKeyValueStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}

    async def exists(self, key: str) -> int:
        self._purge_expired_key(key)
        return 1 if key in self._values else 0

    async def get(self, key: str) -> str | None:
        self._purge_expired_key(key)
        return self._values.get(key)

    async def set(self, key: str, value: str) -> bool:
        self._values[key] = value
        self._expires_at.pop(key, None)
        return True

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        if seconds <= 0:
            await self.delete(key)
            return True

        self._values[key] = value
        self._expires_at[key] = monotonic() + seconds
        return True

    async def incr(self, key: str) -> int:
        self._purge_expired_key(key)
        value = int(self._values.get(key, "0")) + 1
        self._values[key] = str(value)
        return value

    async def expire(self, key: str, seconds: int) -> bool:
        self._purge_expired_key(key)
        if key not in self._values:
            return False

        if seconds <= 0:
            await self.delete(key)
            return True

        self._expires_at[key] = monotonic() + seconds
        return True

    async def delete(self, key: str) -> int:
        existed = key in self._values
        self._values.pop(key, None)
        self._expires_at.pop(key, None)
        return 1 if existed else 0

    def _purge_expired_key(self, key: str) -> None:
        expires_at = self._expires_at.get(key)
        if expires_at is not None and expires_at <= monotonic():
            self._values.pop(key, None)
            self._expires_at.pop(key, None)
