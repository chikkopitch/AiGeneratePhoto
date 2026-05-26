from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Generation, GenerationStatus


class GenerationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_generation(self, user_id: int, prompt: str) -> Generation:
        generation = Generation(
            user_id=user_id,
            prompt=prompt,
            status=GenerationStatus.PENDING.value,
        )
        self._session.add(generation)
        await self._session.flush()
        return generation

    async def set_processing(self, generation_id: int) -> Generation:
        generation = await self._get_required(generation_id)
        generation.status = GenerationStatus.PROCESSING.value
        generation.error_message = None
        await self._session.flush()
        return generation

    async def set_completed(self, generation_id: int, image_url: str) -> Generation:
        generation = await self._get_required(generation_id)
        generation.status = GenerationStatus.COMPLETED.value
        generation.image_url = image_url
        generation.error_message = None
        await self._session.flush()
        return generation

    async def set_failed(self, generation_id: int, error_message: str) -> Generation:
        generation = await self._get_required(generation_id)
        generation.status = GenerationStatus.FAILED.value
        generation.error_message = error_message[:2000]
        await self._session.flush()
        return generation

    async def get_user_generations(
        self,
        user_id: int,
        limit: int = 10,
    ) -> Sequence[Generation]:
        result = await self._session.execute(
            select(Generation)
            .where(Generation.user_id == user_id)
            .order_by(Generation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_active_generation(self, user_id: int) -> Generation | None:
        result = await self._session.execute(
            select(Generation)
            .where(
                Generation.user_id == user_id,
                Generation.status.in_(
                    [
                        GenerationStatus.PENDING.value,
                        GenerationStatus.PROCESSING.value,
                    ]
                ),
            )
            .order_by(Generation.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_completed_generation(self, user_id: int) -> Generation | None:
        result = await self._session.execute(
            select(Generation)
            .where(
                Generation.user_id == user_id,
                Generation.status == GenerationStatus.COMPLETED.value,
                Generation.image_url.is_not(None),
            )
            .order_by(Generation.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_generations(self) -> int:
        result = await self._session.execute(select(func.count(Generation.id)))
        return int(result.scalar_one())

    async def count_by_status(self, status: GenerationStatus | str) -> int:
        status_value = status.value if isinstance(status, GenerationStatus) else status
        result = await self._session.execute(
            select(func.count(Generation.id)).where(Generation.status == status_value)
        )
        return int(result.scalar_one())

    async def count_created_since(self, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count(Generation.id)).where(Generation.created_at >= since)
        )
        return int(result.scalar_one())

    async def get_by_id(self, generation_id: int) -> Generation | None:
        result = await self._session.execute(
            select(Generation).where(Generation.id == generation_id)
        )
        return result.scalar_one_or_none()

    async def _get_required(self, generation_id: int) -> Generation:
        generation = await self.get_by_id(generation_id)
        if generation is None:
            raise ValueError(f"Generation {generation_id} not found")
        return generation

GenerationRepository = GenerationsRepository
