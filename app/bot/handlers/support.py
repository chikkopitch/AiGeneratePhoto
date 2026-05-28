import logging
from datetime import datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import SUPPORT_CALLBACK, main_menu_keyboard
from app.bot.states import SupportForm
from app.config import Settings
from app.services import KeyValueStore, RateLimitService

logger = logging.getLogger(__name__)
router = Router(name="support")

SUPPORT_MESSAGE_MAP_KEY = "support:message:{message_id}"

SUPPORT_PROMPT_TEXT = "Опишите вашу проблему одним сообщением. Мы передадим её оператору."
SUPPORT_UNAVAILABLE_TEXT = "Поддержка временно недоступна."
SUPPORT_THROTTLED_TEXT = "Вы уже отправляли обращение. Попробуйте ещё раз через 60 секунд."
SUPPORT_SENT_TEXT = "Спасибо! Мы передали ваше сообщение в поддержку."


@router.message(Command("support"))
async def support_command_handler(
    message: Message,
    state: FSMContext,
    settings: Settings,
) -> None:
    await start_support_flow(message=message, state=state, settings=settings)


@router.callback_query(F.data == SUPPORT_CALLBACK)
async def support_callback_handler(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    await callback.answer()
    if callback.message is not None:
        await start_support_flow(message=callback.message, state=state, settings=settings)


@router.message(SupportForm.waiting_for_message, F.text)
async def support_message_handler(
    message: Message,
    state: FSMContext,
    settings: Settings,
    rate_limit_service: RateLimitService,
    key_value_store: KeyValueStore,
    bot: Bot,
) -> None:
    if message.from_user is None or message.text is None:
        await message.answer("Не удалось принять обращение. Отправьте текст одним сообщением.")
        return

    if settings.support_chat_id is None:
        await state.clear()
        await message.answer(SUPPORT_UNAVAILABLE_TEXT, reply_markup=main_menu_keyboard())
        return

    can_contact, reason = await rate_limit_service.can_contact_support(message.from_user.id)
    if not can_contact:
        await state.clear()
        await message.answer(reason or SUPPORT_THROTTLED_TEXT, reply_markup=main_menu_keyboard())
        return

    try:
        support_message = await bot.send_message(
            chat_id=settings.support_chat_id,
            text=build_support_request_text(message),
        )
    except TelegramAPIError:
        logger.exception("Failed to forward support request")
        await state.clear()
        await message.answer(SUPPORT_UNAVAILABLE_TEXT, reply_markup=main_menu_keyboard())
        return
    await rate_limit_service.mark_support_contact(message.from_user.id)
    await key_value_store.set(
        SUPPORT_MESSAGE_MAP_KEY.format(message_id=support_message.message_id),
        str(message.from_user.id),
    )

    logger.info("Support request forwarded", extra={"support_message_id": support_message.message_id})
    await state.clear()
    await message.answer(SUPPORT_SENT_TEXT, reply_markup=main_menu_keyboard())


@router.message(SupportForm.waiting_for_message)
async def invalid_support_message_handler(message: Message) -> None:
    await message.answer("Отправьте обращение текстом одним сообщением.")


@router.message(Command("reply"))
async def support_reply_handler(
    message: Message,
    settings: Settings,
    key_value_store: KeyValueStore,
    bot: Bot,
) -> None:
    if settings.support_chat_id is None or message.chat.id != settings.support_chat_id:
        return

    if message.reply_to_message is None:
        await message.answer("Ответьте командой /reply <текст> на сообщение заявки.")
        return

    reply_text = extract_reply_text(message)
    if not reply_text:
        await message.answer("Используйте формат: /reply <текст>")
        return

    telegram_id = await key_value_store.get(
        SUPPORT_MESSAGE_MAP_KEY.format(message_id=message.reply_to_message.message_id)
    )
    if telegram_id is None:
        await message.answer("Не удалось найти пользователя для этой заявки.")
        return

    user_id = int(telegram_id.decode() if isinstance(telegram_id, bytes) else telegram_id)
    try:
        await bot.send_message(chat_id=user_id, text=escape(reply_text))
    except TelegramAPIError:
        logger.exception("Failed to send support reply", extra={"telegram_id": user_id})
        await message.answer("Не удалось отправить ответ пользователю.")
        return

    await message.answer("Ответ отправлен пользователю.")


async def start_support_flow(message: Message, state: FSMContext, settings: Settings) -> None:
    if settings.support_chat_id is None:
        await state.clear()
        await message.answer(SUPPORT_UNAVAILABLE_TEXT, reply_markup=main_menu_keyboard())
        return

    await state.set_state(SupportForm.waiting_for_message)
    await message.answer(SUPPORT_PROMPT_TEXT)


def build_support_request_text(message: Message) -> str:
    if message.from_user is None or message.text is None:
        raise ValueError("Support request requires text and from_user")

    telegram_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "-"
    first_name = message.from_user.first_name or "-"
    created_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_link = f"tg://user?id={telegram_id}"

    return (
        "<b>Новая заявка в поддержку</b>\n"
        f"Дата: {escape(created_at)}\n"
        f"Telegram ID: <code>{telegram_id}</code>\n"
        f"Username: {escape(username)}\n"
        f"First name: {escape(first_name)}\n"
        f"Ссылка: <a href=\"{user_link}\">открыть профиль</a>\n\n"
        f"Текст обращения:\n{escape(message.text)}"
    )


def extract_reply_text(message: Message) -> str:
    if message.text is None:
        return ""

    parts = message.text.split(maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""
