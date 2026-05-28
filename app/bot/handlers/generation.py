import logging
from io import BytesIO

from aiogram import Bot, F, Router
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
    MAX_REFERENCE_IMAGES,
    PromptValidationError,
    RateLimitService,
)

logger = logging.getLogger(__name__)
router = Router(name="generation")

PROMPT_TEXT = (
    "Опишите фотосессию текстом или пришлите фото, которое нужно отредактировать. "
    "Если отправляете фото, можно добавить инструкцию в подписи."
)
EDIT_PROMPT_TEXT = "Фото загружено. Напишите, что нужно изменить, или пришлите ещё фото."
ALREADY_GENERATING_TEXT = "Генерация уже идёт. Дождитесь результата."
REFERENCE_IMAGE_URLS_KEY = "reference_image_urls"
MAX_REFERENCE_IMAGE_BYTES = 20 * 1024 * 1024


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

    await generate_from_prompt(
        message=message,
        state=state,
        session=session,
        generation_service=generation_service,
        rate_limit_service=rate_limit_service,
        prompt=message.text,
    )


@router.message(PhotoSessionForm.waiting_for_prompt, F.photo)
@router.message(PhotoSessionForm.waiting_for_edit_prompt, F.photo)
async def photo_upload_handler(
    message: Message,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
    generation_service: GenerationService,
    rate_limit_service: RateLimitService,
) -> None:
    await handle_reference_image_upload(
        message=message,
        bot=bot,
        state=state,
        session=session,
        generation_service=generation_service,
        rate_limit_service=rate_limit_service,
    )


@router.message(PhotoSessionForm.waiting_for_prompt, F.document)
@router.message(PhotoSessionForm.waiting_for_edit_prompt, F.document)
async def image_document_upload_handler(
    message: Message,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
    generation_service: GenerationService,
    rate_limit_service: RateLimitService,
) -> None:
    if not is_image_document(message):
        await message.answer("Пришлите фото или файл-изображение.", reply_markup=prompt_keyboard())
        return

    await handle_reference_image_upload(
        message=message,
        bot=bot,
        state=state,
        session=session,
        generation_service=generation_service,
        rate_limit_service=rate_limit_service,
    )


@router.message(PhotoSessionForm.waiting_for_edit_prompt, F.text)
async def edit_prompt_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    generation_service: GenerationService,
    rate_limit_service: RateLimitService,
) -> None:
    if message.from_user is None or message.text is None:
        await message.answer("Не удалось принять описание правки. Попробуйте ещё раз.")
        return

    image_urls = await get_reference_image_urls(state)
    if not image_urls:
        await state.clear()
        await message.answer(
            "Не удалось найти загруженное фото. Начните заново и пришлите фото ещё раз.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await generate_from_prompt(
        message=message,
        state=state,
        session=session,
        generation_service=generation_service,
        rate_limit_service=rate_limit_service,
        prompt=message.text,
        image_urls=image_urls,
    )


async def handle_reference_image_upload(
    message: Message,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
    generation_service: GenerationService,
    rate_limit_service: RateLimitService,
) -> None:
    if message.from_user is None:
        await message.answer("Не удалось принять фото. Попробуйте ещё раз.")
        return

    can_generate, reason = await rate_limit_service.can_generate(message.from_user.id)
    if not can_generate:
        await state.clear()
        await message.answer(reason or ALREADY_GENERATING_TEXT, reply_markup=main_menu_keyboard())
        return

    image_urls = await get_reference_image_urls(state)
    if len(image_urls) >= MAX_REFERENCE_IMAGES:
        await message.answer(
            f"Можно загрузить не больше {MAX_REFERENCE_IMAGES} фото для одной правки.",
            reply_markup=prompt_keyboard(),
        )
        return

    try:
        uploaded_url = await upload_telegram_image(
            message=message,
            bot=bot,
            generation_service=generation_service,
        )
    except ReferenceImageError as exc:
        await message.answer(str(exc), reply_markup=prompt_keyboard())
        return
    except GenerationError:
        logger.exception(
            "Failed to upload reference image",
            extra={"telegram_id": message.from_user.id, "status": "upload_failed"},
        )
        await message.answer(
            "Не удалось загрузить фото для редактирования. Попробуйте отправить другое изображение.",
            reply_markup=prompt_keyboard(),
        )
        return

    image_urls.append(uploaded_url)
    await state.set_state(PhotoSessionForm.waiting_for_edit_prompt)
    await state.update_data(**{REFERENCE_IMAGE_URLS_KEY: image_urls})

    caption = (message.caption or "").strip()
    if caption:
        await generate_from_prompt(
            message=message,
            state=state,
            session=session,
            generation_service=generation_service,
            rate_limit_service=rate_limit_service,
            prompt=caption,
            image_urls=image_urls,
        )
        return

    await message.answer(EDIT_PROMPT_TEXT, reply_markup=prompt_keyboard())


async def generate_from_prompt(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    generation_service: GenerationService,
    rate_limit_service: RateLimitService,
    prompt: str,
    image_urls: list[str] | None = None,
) -> None:
    if message.from_user is None:
        await message.answer("Не удалось принять описание. Попробуйте ещё раз.")
        return

    is_edit = image_urls is not None
    prompt = prompt.strip()
    try:
        validated_prompt = generation_service.validate_prompt(prompt)
    except PromptValidationError as exc:
        if not is_edit:
            await state.clear()
        await message.answer(
            prompt_validation_message(exc),
            reply_markup=prompt_keyboard() if is_edit else main_menu_keyboard(),
        )
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
        await message.answer("Редактирую фото..." if is_edit else "Генерирую изображение...")

        if is_edit:
            image_url = await generation_service.generate_edited_image(
                validated_prompt,
                image_urls or [],
            )
        else:
            image_url = await generation_service.generate_image(validated_prompt)
        try:
            await message.answer_photo(
                photo=URLInputFile(image_url),
                caption="Готово. Фото отредактировано." if is_edit else "Готово. Ваша AI-фотосессия.",
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


class ReferenceImageError(Exception):
    pass


async def get_reference_image_urls(state: FSMContext) -> list[str]:
    data = await state.get_data()
    image_urls = data.get(REFERENCE_IMAGE_URLS_KEY, [])
    if not isinstance(image_urls, list):
        return []
    return [
        image_url.strip()
        for image_url in image_urls
        if isinstance(image_url, str) and image_url.strip()
    ]


async def upload_telegram_image(
    message: Message,
    bot: Bot,
    generation_service: GenerationService,
) -> str:
    file_id, filename, content_type, file_size = extract_telegram_image(message)
    if file_size is not None and file_size > MAX_REFERENCE_IMAGE_BYTES:
        raise ReferenceImageError("Файл слишком большой. Максимальный размер изображения: 20 МБ.")

    destination = BytesIO()
    try:
        await bot.download(file_id, destination=destination)
    except Exception as exc:
        raise ReferenceImageError("Не удалось скачать фото из Telegram. Попробуйте ещё раз.") from exc

    file_bytes = destination.getvalue()
    if not file_bytes:
        raise ReferenceImageError("Не удалось скачать фото из Telegram. Попробуйте ещё раз.")
    if len(file_bytes) > MAX_REFERENCE_IMAGE_BYTES:
        raise ReferenceImageError("Файл слишком большой. Максимальный размер изображения: 20 МБ.")

    return await generation_service.upload_reference_image(
        file_bytes=file_bytes,
        filename=filename,
        content_type=content_type,
    )


def extract_telegram_image(message: Message) -> tuple[str, str, str, int | None]:
    if message.photo:
        photo = message.photo[-1]
        filename = f"telegram-photo-{photo.file_unique_id}.jpg"
        return photo.file_id, filename, "image/jpeg", photo.file_size

    if is_image_document(message) and message.document is not None:
        document = message.document
        filename = document.file_name or f"telegram-image-{document.file_unique_id}"
        content_type = document.mime_type or "application/octet-stream"
        return document.file_id, filename, content_type, document.file_size

    raise ReferenceImageError("Пришлите фото или файл-изображение.")


def is_image_document(message: Message) -> bool:
    return (
        message.document is not None
        and message.document.mime_type is not None
        and message.document.mime_type.startswith("image/")
    )


@router.message(PhotoSessionForm.waiting_for_prompt)
async def invalid_prompt_handler(message: Message) -> None:
    await message.answer(
        "Пришлите текстовое описание фотосессии или фото для редактирования.",
        reply_markup=prompt_keyboard(),
    )


@router.message(PhotoSessionForm.waiting_for_edit_prompt)
async def invalid_edit_prompt_handler(message: Message) -> None:
    await message.answer(
        "Напишите текстом, что изменить на фото, или отправьте ещё одно фото.",
        reply_markup=prompt_keyboard(),
    )


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
