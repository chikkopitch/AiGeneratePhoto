from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.bot.handlers.menu import WELCOME_TEXT, start_handler
from app.bot.keyboards import CREATE_SESSION_CALLBACK, HISTORY_CALLBACK
from app.database.base import Base
from app.database.repositories.users import UsersRepository


@dataclass
class DummyUser:
    id: int
    username: str | None
    first_name: str | None


class DummyMessage:
    def __init__(self) -> None:
        self.from_user = DummyUser(
            id=123456789,
            username="photo_user",
            first_name="Alex",
        )
        self.answers: list[tuple[str, InlineKeyboardMarkup | None]] = []

    async def answer(
        self,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        self.answers.append((text, reply_markup))


class DummyState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_start_handler_registers_user_and_shows_main_menu(
    session: AsyncSession,
) -> None:
    message = DummyMessage()
    state = DummyState()

    await start_handler(message, session, state)  # type: ignore[arg-type]

    user = await UsersRepository(session).get_by_telegram_id(123456789)
    assert user is not None
    assert user.username == "photo_user"
    assert state.cleared is True
    assert message.answers[0][0] == WELCOME_TEXT

    keyboard = message.answers[0][1]
    assert keyboard is not None
    callback_data = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]
    assert CREATE_SESSION_CALLBACK in callback_data
    assert HISTORY_CALLBACK in callback_data
