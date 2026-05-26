import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, URLInputFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    CREATE_AGAIN_CALLBACK,
    CREATE_SESSION_CALLBACK,
    TRY_AGAIN_CALLBACK,
    after_generation_keyboard,
    main_menu_keyboard,
    prompt_keyboard,
    retry_keyboard,
)
from app.bot.states import PhotoSessionForm
from app.database.repositories import GenerationsRepository, UsersRepository
from app.services import (
    GenerationError,
    GenerationService,
    PromptValidationError,
    RateLimitService,
)

logger = logging.getLogger(__name__)
router = Router(name="generation")

PROMPT_TEXT = "Опишите фотосессию: стиль, внешность, одежду, локацию, настроение, освещение."
ALREADY_GENERATING_TEXT = "Генерация уже идёт. Дождитесь результата."


@router.callback_query(F.data.in_({CREATE_SESSION_CALLBACK, CREATE_AGAIN_CALLBACK, TRY_AGAIN_CALLBACK}))
async def create_session_callback_handler(
    callback: CallbackQuery,
    state: FSMContext,
    rate_limit_service: RateLimitService,
) -> None:
    can_generate, reason = await rate_limit_service.can_generate(callback.from_user.id)
    if not can_generate:
        await callback.answer(reason or ALREADY_GENERATING_TEXT, show_alert=True)
        return

    await state.set_state(PhotoSessionForm.waiting_for_prompt)
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(PROMPT_TEXT, reply_markup=prompt_keyboard())


@router.message(PhotoSessionForm.waiting_for_prompt, F.text)
async def prompt_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    generation_service: GenerationService,
    rate_limit_service: RateLimitService,
) -> None:
    if message.from_user is None or message.text is None:
        await message.answer("Не удалось принять описание. Попробуйте ещё раз.")
        return

    prompt = message.text.strip()
    try:
        validated_prompt = generation_service.validate_prompt(prompt)
    except PromptValidationError as exc:
        await state.clear()
        await message.answer(prompt_validation_message(exc), reply_markup=main_menu_keyboard())
        return

    can_generate, reason = await rate_limit_service.can_generate(message.from_user.id)
    if not can_generate:
        await state.clear()
        await message.answer(reason or ALREADY_GENERATING_TEXT, reply_markup=main_menu_keyboard())
        return

    users_repository = UsersRepository(session)
    generations_repository = GenerationsRepository(session)
    user = await users_repository.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    generation = await generations_repository.create_generation(user_id=user.id, prompt=validated_prompt)
    await session.commit()

    await state.set_state(PhotoSessionForm.generating)
    await state.update_data(generation_id=generation.id)
    await rate_limit_service.mark_generation_started(message.from_user.id)

    try:
        await generations_repository.set_processing(generation.id)
        await session.commit()
        await message.answer("Генерирую изображение...")

        image_url = await generation_service.generate_image(validated_prompt)
        try:
            await message.answer_photo(
                photo=URLInputFile(image_url),
                caption="Готово. Ваша AI-фотосессия.",
            )
        except TelegramBadRequest as exc:
            logger.exception(
                "Telegram failed to send generated photo",
                extra={
                    "telegram_id": message.from_user.id,
                    "generation_id": generation.id,
                    "status": "photo_send_failed",
                    "error_type": type(exc).__name__,
                },
            )
            await message.answer(
                f"Изображение готово, но Telegram не смог загрузить фото. Ссылка: {image_url}"
            )
        await generations_repository.set_completed(generation.id, image_url)
        await session.commit()
        await state.clear()
        await message.answer("Что дальше?", reply_markup=after_generation_keyboard())
    except Exception as exc:
        await save_failed_generation(session, generations_repository, generation.id, exc)
        await state.clear()
        await message.answer(
            "Не удалось создать изображение. Попробуйте изменить описание или повторить позже.",
            reply_markup=retry_keyboard(),
        )
    finally:
        await rate_limit_service.mark_generation_finished(message.from_user.id)


@router.message(PhotoSessionForm.waiting_for_prompt)
async def invalid_prompt_handler(message: Message) -> None:
    await message.answer("Пришлите текстовое описание фотосессии.", reply_markup=prompt_keyboard())


@router.message(PhotoSessionForm.generating)
async def generating_state_handler(message: Message) -> None:
    await message.answer(ALREADY_GENERATING_TEXT, reply_markup=main_menu_keyboard())


async def save_failed_generation(
    session: AsyncSession,
    repository: GenerationsRepository,
    generation_id: int,
    exc: Exception,
) -> None:
    logger.exception(
        "Generation failed",
        extra={
            "generation_id": generation_id,
            "request_id": getattr(exc, "request_id", "-") or "-",
            "status": getattr(exc, "status", "failed") or "failed",
            "error_type": type(exc).__name__,
        },
    )
    try:
        await repository.set_failed(generation_id, str(exc))
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.exception(
            "Failed to save failed generation status",
            extra={"generation_id": generation_id, "status": "db_error", "error_type": "SQLAlchemyError"},
        )


def prompt_validation_message(exc: PromptValidationError) -> str:
    message = str(exc)
    if "empty" in message.casefold():
        return "Описание не должно быть пустым."
    if "at least" in message.casefold():
        return "Описание слишком короткое. Добавьте больше деталей."
    if "no more" in message.casefold():
        return "Описание слишком длинное. Сократите его до 1500 символов."
    return "Описание не подходит для генерации. Измените текст и попробуйте снова."
