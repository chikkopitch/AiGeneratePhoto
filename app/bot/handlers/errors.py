import logging

from aiogram import Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery, ErrorEvent, Message, Update
from sqlalchemy.exc import SQLAlchemyError

from app.services import (
    GenerationInvalidResponseError,
    GenerationProviderError,
    GenerationTimeoutError,
    PromptValidationError,
)
from app.services.wavespeed import (
    WavespeedAPIError,
    WavespeedInvalidResponseError,
    WavespeedTimeoutError,
)

logger = logging.getLogger(__name__)
router = Router(name="errors")


@router.errors()
async def global_error_handler(event: ErrorEvent) -> bool:
    exception = event.exception
    message, callback = extract_update_target(event.update)
    telegram_id = extract_telegram_id(message, callback)

    logger.exception(
        "Unhandled handler exception",
        exc_info=(type(exception), exception, exception.__traceback__),
        extra={
            "telegram_id": telegram_id or "-",
            "generation_id": getattr(exception, "generation_id", "-") or "-",
            "request_id": getattr(exception, "request_id", "-") or "-",
            "status": getattr(exception, "status", "failed") or "failed",
            "error_type": type(exception).__name__,
        },
    )

    user_message = build_user_error_message(exception)
    try:
        if callback is not None:
            await callback.answer()
        if message is not None:
            await message.answer(user_message)
        elif callback is not None and callback.message is not None:
            await callback.message.answer(user_message)
    except TelegramAPIError as send_error:
        logger.exception(
            "Failed to send error message to user",
            extra={
                "telegram_id": telegram_id or "-",
                "status": "telegram_error",
                "error_type": type(send_error).__name__,
            },
        )

    return True


def build_user_error_message(exception: Exception) -> str:
    if isinstance(exception, PromptValidationError):
        message = str(exception).casefold()
        if "empty" in message:
            return "Описание не должно быть пустым."
        if "at least" in message:
            return "Описание слишком короткое. Добавьте больше деталей."
        if "no more" in message:
            return "Описание слишком длинное. Сократите его до 1500 символов."
        return "Описание не подходит для генерации. Измените текст и попробуйте снова."

    if isinstance(exception, (GenerationTimeoutError, WavespeedTimeoutError)):
        return "Генерация заняла слишком много времени. Попробуйте позже."

    if isinstance(exception, (GenerationInvalidResponseError, WavespeedInvalidResponseError)):
        return "Сервис генерации вернул неожиданный ответ. Попробуйте позже."

    if isinstance(exception, (GenerationProviderError, WavespeedAPIError)):
        return "Сервис генерации временно недоступен. Попробуйте позже."

    if isinstance(exception, SQLAlchemyError):
        return "Не удалось сохранить данные. Попробуйте позже."

    if isinstance(exception, TelegramBadRequest):
        return "Telegram не смог обработать сообщение. Попробуйте позже."

    return "Произошла ошибка. Попробуйте позже."


def extract_update_target(update: Update) -> tuple[Message | None, CallbackQuery | None]:
    if update.message is not None:
        return update.message, None
    if update.callback_query is not None:
        return None, update.callback_query
    return None, None


def extract_telegram_id(message: Message | None, callback: CallbackQuery | None) -> int | None:
    if message is not None and message.from_user is not None:
        return message.from_user.id
    if callback is not None:
        return callback.from_user.id
    return None
