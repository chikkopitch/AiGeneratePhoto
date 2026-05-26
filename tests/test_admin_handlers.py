from dataclasses import dataclass

import pytest

from app.bot.handlers.admin import is_admin, send_broadcast


@dataclass
class DummySettings:
    admin_ids: list[int]


class DummyBot:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent_messages.append((chat_id, text))


def test_is_admin_checks_admin_ids() -> None:
    settings = DummySettings(admin_ids=[1, 2])

    assert is_admin(1, settings) is True  # type: ignore[arg-type]
    assert is_admin(3, settings) is False  # type: ignore[arg-type]
    assert is_admin(None, settings) is False  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_send_broadcast_sends_to_all_users(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("app.bot.handlers.admin.asyncio.sleep", no_sleep)
    bot = DummyBot()

    sent_count, error_count = await send_broadcast(  # type: ignore[arg-type]
        bot=bot,
        telegram_ids=[10, 20],
        text="hello",
    )

    assert sent_count == 2
    assert error_count == 0
    assert bot.sent_messages == [(10, "hello"), (20, "hello")]
