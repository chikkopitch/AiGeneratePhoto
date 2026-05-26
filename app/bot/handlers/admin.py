import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states import AdminBroadcastForm
from app.config import Settings
from app.database.models import GenerationStatus
from app.database.repositories import GenerationsRepository, UsersRepository

logger = logging.getLogger(__name__)
router = Router(name="admin")

BROADCAST_SEND_CALLBACK = "admin:broadcast:send"
BROADCAST_CANCEL_CALLBACK = "admin:broadcast:cancel"
BROADCAST_SLEEP_SECONDS = 0.05


def is_admin(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id in settings.admin_ids


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="Рассылка", callback_data="admin:broadcast")],
        ]
    )


def broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отправить", callback_data=BROADCAST_SEND_CALLBACK)],
            [InlineKeyboardButton(text="Отмена", callback_data=BROADCAST_CANCEL_CALLBACK)],
        ]
    )


@router.message(Command("admin"))
async def admin_command_handler(message: Message, settings: Settings) -> None:
    if not is_admin(message.from_user.id if message.from_user else None, settings):
        return

    await message.answer("Меню администратора.", reply_markup=admin_menu_keyboard())


@router.message(Command("stats"))
async def stats_command_handler(
    message: Message,
    settings: Settings,
    session: AsyncSession,
) -> None:
    if not is_admin(message.from_user.id if message.from_user else None, settings):
        return

    await message.answer(await build_stats_text(session))


@router.message(Command("broadcast"))
async def broadcast_command_handler(
    message: Message,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not is_admin(message.from_user.id if message.from_user else None, settings):
        return

    await state.set_state(AdminBroadcastForm.waiting_for_text)
    await message.answer("Введите текст рассылки.")


@router.callback_query(F.data == "admin:stats")
async def stats_callback_handler(
    callback: CallbackQuery,
    settings: Settings,
    session: AsyncSession,
) -> None:
    if not is_admin(callback.from_user.id, settings):
        await callback.answer()
        return

    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(await build_stats_text(session))


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_callback_handler(
    callback: CallbackQuery,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not is_admin(callback.from_user.id, settings):
        await callback.answer()
        return

    await state.set_state(AdminBroadcastForm.waiting_for_text)
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer("Введите текст рассылки.")


@router.message(AdminBroadcastForm.waiting_for_text, F.text)
async def broadcast_text_handler(
    message: Message,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not is_admin(message.from_user.id if message.from_user else None, settings):
        return

    broadcast_text = (message.text or "").strip()
    if not broadcast_text:
        await message.answer("Текст рассылки не должен быть пустым.")
        return

    await state.update_data(broadcast_text=broadcast_text)
    await state.set_state(AdminBroadcastForm.waiting_for_confirmation)
    await message.answer(
        f"Preview:\n\n{broadcast_text}",
        reply_markup=broadcast_preview_keyboard(),
    )


@router.message(AdminBroadcastForm.waiting_for_text)
async def invalid_broadcast_text_handler(message: Message) -> None:
    await message.answer("Отправьте текст рассылки одним сообщением.")


@router.callback_query(F.data == BROADCAST_CANCEL_CALLBACK)
async def broadcast_cancel_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer("Рассылка отменена.")


@router.callback_query(F.data == BROADCAST_SEND_CALLBACK)
async def broadcast_send_callback_handler(
    callback: CallbackQuery,
    settings: Settings,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    if not is_admin(callback.from_user.id, settings):
        await callback.answer()
        return

    data = await state.get_data()
    broadcast_text = str(data.get("broadcast_text") or "").strip()
    if not broadcast_text:
        await state.clear()
        await callback.answer()
        if callback.message is not None:
            await callback.message.answer("Текст рассылки не найден. Запустите /broadcast заново.")
        return

    await callback.answer()
    if callback.message is not None:
        await callback.message.answer("Рассылка запущена.")

    telegram_ids = await UsersRepository(session).get_all_telegram_ids()
    sent_count, error_count = await send_broadcast(bot, telegram_ids, broadcast_text)
    await state.clear()

    if callback.message is not None:
        await callback.message.answer(
            f"Рассылка завершена.\nОтправлено: {sent_count}\nОшибок: {error_count}"
        )


async def build_stats_text(session: AsyncSession) -> str:
    users_repository = UsersRepository(session)
    generations_repository = GenerationsRepository(session)
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = await users_repository.count_users()
    total_generations = await generations_repository.count_generations()
    successful_generations = await generations_repository.count_by_status(GenerationStatus.COMPLETED)
    failed_generations = await generations_repository.count_by_status(GenerationStatus.FAILED)
    generations_today = await generations_repository.count_created_since(today_start)

    return (
        "Статистика:\n"
        f"Всего пользователей: {total_users}\n"
        f"Всего генераций: {total_generations}\n"
        f"Successful generations: {successful_generations}\n"
        f"Failed generations: {failed_generations}\n"
        f"Generations today: {generations_today}"
    )


async def send_broadcast(
    bot: Bot,
    telegram_ids: Sequence[int],
    text: str,
) -> tuple[int, int]:
    sent_count = 0
    error_count = 0

    for telegram_id in telegram_ids:
        try:
            await bot.send_message(chat_id=telegram_id, text=text)
            sent_count += 1
        except TelegramAPIError:
            error_count += 1
            logger.exception("Broadcast delivery failed", extra={"telegram_id": telegram_id})

        await asyncio.sleep(BROADCAST_SLEEP_SECONDS)

    return sent_count, error_count
