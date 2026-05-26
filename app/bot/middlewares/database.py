from collections.abc import Awaitable, Callable
import logging
from typing import Any

from aiogram import BaseMiddleware
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


class DatabaseSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            data["session"] = session
            try:
                return await handler(event, data)
            except SQLAlchemyError as exc:
                await session.rollback()
                logger.exception(
                    "Database error during update handling",
                    extra={"status": "db_error", "error_type": type(exc).__name__},
                )
                raise
            except Exception:
                await session.rollback()
                raise
