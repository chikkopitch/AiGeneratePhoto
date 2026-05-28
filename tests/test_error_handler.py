from sqlalchemy.exc import SQLAlchemyError

from app.bot.handlers.errors import build_user_error_message
from app.services.generation import (
    GenerationInvalidResponseError,
    GenerationProviderError,
    GenerationTimeoutError,
    PromptValidationError,
)


def test_build_user_error_message_for_prompt_validation() -> None:
    assert build_user_error_message(PromptValidationError("Prompt is empty")) == (
        "Описание не должно быть пустым."
    )
    assert build_user_error_message(PromptValidationError("Prompt must contain no more")) == (
        "Описание слишком длинное. Сократите его до 1500 символов."
    )


def test_build_user_error_message_for_generation_errors() -> None:
    assert build_user_error_message(GenerationTimeoutError("timeout")) == (
        "Генерация заняла слишком много времени. Попробуйте позже."
    )
    assert build_user_error_message(GenerationInvalidResponseError("bad")) == (
        "Сервис генерации вернул неожиданный ответ. Попробуйте позже."
    )
    assert build_user_error_message(GenerationProviderError("bad")) == (
        "Сервис генерации временно недоступен. Попробуйте позже."
    )


def test_build_user_error_message_for_infrastructure_errors() -> None:
    assert build_user_error_message(SQLAlchemyError("db")) == (
        "Не удалось сохранить данные. Попробуйте позже."
    )
