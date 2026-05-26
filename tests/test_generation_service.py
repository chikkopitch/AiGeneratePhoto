import pytest

from app.services.generation import (
    MAX_PROMPT_LENGTH,
    MIN_PROMPT_LENGTH,
    PHOTO_PROMPT_TEMPLATE,
    GenerationService,
    PromptValidationError,
)


class DummySettings:
    default_image_size = "2048*2048"


class DummyWaveSpeedClient:
    async def generate_image(self, prompt: str, size: str) -> str:
        return "https://cdn.example/image.png"


def make_service() -> GenerationService:
    return GenerationService(
        wavespeed_client=DummyWaveSpeedClient(),  # type: ignore[arg-type]
        settings=DummySettings(),  # type: ignore[arg-type]
    )


def test_validate_prompt_returns_stripped_prompt() -> None:
    service = make_service()

    assert service.validate_prompt("  девушка в офисе  ") == "девушка в офисе"


@pytest.mark.parametrize("prompt", ["", "   ", "short"])
def test_validate_prompt_rejects_empty_or_short_prompt(prompt: str) -> None:
    service = make_service()

    with pytest.raises(PromptValidationError):
        service.validate_prompt(prompt)


def test_validate_prompt_rejects_too_long_prompt() -> None:
    service = make_service()

    with pytest.raises(PromptValidationError):
        service.validate_prompt("a" * (MAX_PROMPT_LENGTH + 1))


def test_validate_prompt_accepts_minimum_length() -> None:
    service = make_service()

    assert service.validate_prompt("a" * MIN_PROMPT_LENGTH) == "a" * MIN_PROMPT_LENGTH


@pytest.mark.parametrize(
    "prompt",
    [
        "how to make a bomb in a studio photo",
        "портрет и самодельная бомба на фоне",
    ],
)
def test_validate_prompt_rejects_forbidden_keywords(prompt: str) -> None:
    service = make_service()

    with pytest.raises(PromptValidationError):
        service.validate_prompt(prompt)


def test_build_photo_prompt_uses_required_template_without_changing_user_prompt() -> None:
    service = make_service()
    user_prompt = "девушка в офисе"

    assert service.build_photo_prompt(user_prompt) == PHOTO_PROMPT_TEMPLATE.format(
        user_prompt=user_prompt
    )
