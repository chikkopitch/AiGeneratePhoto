from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User


class UsersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
            )
            self._session.add(user)
        else:
            user.username = username
            user.first_name = first_name

        await self._session.flush()
        return user

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def count_users(self) -> int:
        result = await self._session.execute(select(func.count(User.id)))
        return int(result.scalar_one())

    async def get_all_telegram_ids(self) -> Sequence[int]:
        result = await self._session.execute(select(User.telegram_id).order_by(User.id.asc()))
        return result.scalars().all()


UserRepository = UsersRepository
