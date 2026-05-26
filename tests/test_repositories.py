from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.base import Base
from app.database.models import GenerationStatus
from app.database.repositories.generations import GenerationsRepository
from app.database.repositories.users import UsersRepository


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
async def test_users_repository_creates_user(session: AsyncSession) -> None:
    repository = UsersRepository(session)

    user = await repository.get_or_create_user(
        telegram_id=123456789,
        username="photo_user",
        first_name="Alex",
    )

    assert user.id is not None
    assert user.telegram_id == 123456789
    assert user.username == "photo_user"
    assert user.first_name == "Alex"

    saved_user = await repository.get_by_telegram_id(123456789)

    assert saved_user is not None
    assert saved_user.id == user.id


@pytest.mark.asyncio
async def test_generations_repository_lifecycle(session: AsyncSession) -> None:
    users_repository = UsersRepository(session)
    generations_repository = GenerationsRepository(session)
    user = await users_repository.get_or_create_user(
        telegram_id=123456789,
        username="photo_user",
        first_name="Alex",
    )

    generation = await generations_repository.create_generation(
        user_id=user.id,
        prompt="portrait in a bright studio",
    )

    assert generation.id is not None
    assert generation.user_id == user.id
    assert generation.prompt == "portrait in a bright studio"
    assert generation.status == GenerationStatus.PENDING.value
    assert generation.image_url is None

    completed_generation = await generations_repository.set_completed(
        generation.id,
        "https://cdn.example/image.png",
    )

    assert completed_generation.status == GenerationStatus.COMPLETED.value
    assert completed_generation.image_url == "https://cdn.example/image.png"
    assert completed_generation.error_message is None

    generations = await generations_repository.get_user_generations(user.id, limit=10)

    assert len(generations) == 1
    assert generations[0].id == generation.id
