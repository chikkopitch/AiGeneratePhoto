from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    HELP_CALLBACK,
    MAIN_MENU_CALLBACK,
    main_menu_keyboard,
)
from app.bot.states import PhotoSessionForm
from app.database.repositories import UsersRepository

router = Router(name="menu")

WELCOME_TEXT = (
    "Привет. Я помогу создать AI-фотосессию по текстовому описанию.\n"
    "Выберите действие в меню."
)
HELP_TEXT = (
    "Чтобы создать фотосессию, нажмите «Создать фотосессию» и отправьте описание: "
    "стиль, внешность, одежду, локацию, настроение и освещение."
)


async def register_user(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return

    await UsersRepository(session).get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    await session.commit()


@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await register_user(message, session)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def help_command_handler(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("cancel"))
async def cancel_command_handler(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state == PhotoSessionForm.generating.state:
        await message.answer(
            "Генерация уже идёт. Дождитесь результата.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == MAIN_MENU_CALLBACK)
async def main_menu_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state != PhotoSessionForm.generating.state:
        await state.clear()

    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == HELP_CALLBACK)
async def help_callback_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())

