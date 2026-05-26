import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, Update

logger = logging.getLogger(__name__)


class IncomingLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        telegram_id, event_type, content_length = self._extract_event_context(event)
        logger.info(
            "Incoming Telegram update",
            extra={
                "telegram_id": telegram_id or "-",
                "status": event_type,
                "content_length": content_length,
            },
        )
        return await handler(event, data)

    @staticmethod
    def _extract_event_context(event: Any) -> tuple[int | None, str, int]:
        if isinstance(event, Update):
            if event.message is not None:
                return IncomingLoggingMiddleware._message_context(event.message)
            if event.callback_query is not None:
                return IncomingLoggingMiddleware._callback_context(event.callback_query)
            return None, "update", 0

        if isinstance(event, Message):
            return IncomingLoggingMiddleware._message_context(event)
        if isinstance(event, CallbackQuery):
            return IncomingLoggingMiddleware._callback_context(event)
        return None, type(event).__name__, 0

    @staticmethod
    def _message_context(message: Message) -> tuple[int | None, str, int]:
        text = message.text or message.caption or ""
        return message.from_user.id if message.from_user else None, "message", len(text)

    @staticmethod
    def _callback_context(callback: CallbackQuery) -> tuple[int | None, str, int]:
        return callback.from_user.id, "callback_query", len(callback.data or "")
