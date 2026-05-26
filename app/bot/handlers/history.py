import logging
from collections.abc import Sequence
from html import escape
from textwrap import shorten

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.types import CallbackQuery, URLInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    HISTORY_CALLBACK,
    SHOW_LAST_IMAGE_CALLBACK,
    history_keyboard,
    main_menu_keyboard,
)
from app.database.models import Generation, GenerationStatus
from app.database.repositories import GenerationsRepository, UsersRepository

logger = logging.getLogger(__name__)
router = Router(name="history")

EMPTY_HISTORY_TEXT = (
    "У вас пока нет генераций. Нажмите ‘Создать фотосессию’, чтобы сделать первую."
)
STATUS_LABELS = {
    GenerationStatus.PENDING.value: "ожидает",
    GenerationStatus.PROCESSING.value: "в работе",
    GenerationStatus.COMPLETED.value: "готова",
    GenerationStatus.FAILED.value: "ошибка",
}


@router.callback_query(F.data == HISTORY_CALLBACK)
async def history_callback_handler(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.message is None:
        return

    user = await UsersRepository(session).get_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.message.answer(EMPTY_HISTORY_TEXT, reply_markup=main_menu_keyboard())
        return

    generations = await GenerationsRepository(session).get_user_generations(user.id, limit=10)
    if not generations:
        await callback.message.answer(EMPTY_HISTORY_TEXT, reply_markup=main_menu_keyboard())
        return

    completed_generation_exists = any(
        generation.status == GenerationStatus.COMPLETED.value and generation.image_url
        for generation in generations
    )
    await callback.message.answer(
        build_history_text(generations),
        reply_markup=history_keyboard(completed_generation_exists),
    )


@router.callback_query(F.data == SHOW_LAST_IMAGE_CALLBACK)
async def show_last_image_callback_handler(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.message is None:
        return

    user = await UsersRepository(session).get_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.message.answer(EMPTY_HISTORY_TEXT, reply_markup=main_menu_keyboard())
        return

    generation = await GenerationsRepository(session).get_latest_completed_generation(user.id)
    if generation is None or not generation.image_url:
        await callback.message.answer(
            "Готовых изображений пока нет.",
            reply_markup=main_menu_keyboard(),
        )
        return

    try:
        await callback.message.answer_photo(
            photo=URLInputFile(generation.image_url),
            caption="Последняя готовая картинка.",
            reply_markup=main_menu_keyboard(),
        )
    except (TelegramBadRequest, TelegramNetworkError):
        logger.exception(
            "Telegram failed to fetch generation image",
            extra={
                "telegram_id": callback.from_user.id,
                "generation_id": generation.id,
                "status": "photo_send_failed",
                "error_type": "TelegramPhotoSendError",
            },
        )
        await callback.message.answer(
            f"Telegram не смог загрузить изображение. Ссылка: {escape(generation.image_url)}",
            reply_markup=main_menu_keyboard(),
        )


def build_history_text(generations: Sequence[Generation]) -> str:
    lines = ["Последние генерации:"]
    for index, generation in enumerate(generations, start=1):
        lines.append(format_generation_line(index, generation))
    return "\n\n".join(lines)


def format_generation_line(index: int, generation: Generation) -> str:
    created_at = (
        generation.created_at.strftime("%d.%m.%Y %H:%M")
        if generation.created_at
        else "-"
    )
    prompt = escape(shorten(generation.prompt, width=80, placeholder="..."))
    status = STATUS_LABELS.get(generation.status, generation.status)
    return f"{index}. {created_at}\n{prompt}\nСтатус: {status}"
