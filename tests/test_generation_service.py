import pytest

from app.services.generation import (
    MAX_PROMPT_LENGTH,
    MAX_REFERENCE_IMAGES,
    MIN_PROMPT_LENGTH,
    PHOTO_EDIT_PROMPT_TEMPLATE,
    PHOTO_PROMPT_TEMPLATE,
    GenerationError,
    GenerationService,
    PromptValidationError,
)


class DummySettings:
    default_image_size = "2048*2048"
    wavespeed_edit_model_path = "bytedance/seedream-v4/edit"


class DummyWaveSpeedClient:
    def __init__(self) -> None:
        self.last_prompt: str | None = None
        self.last_size: str | None = None
        self.last_images: list[str] | None = None
        self.last_model_path: str | None = None

    async def generate_image(
        self,
        prompt: str,
        size: str,
        images: list[str] | None = None,
        model_path: str | None = None,
    ) -> str:
        self.last_prompt = prompt
        self.last_size = size
        self.last_images = images
        self.last_model_path = model_path
        return "https://cdn.example/image.png"

    async def upload_binary_file(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> str:
        return "https://cdn.example/uploaded.png"


def make_service() -> GenerationService:
    return GenerationService(
        wavespeed_client=DummyWaveSpeedClient(),  # type: ignore[arg-type]
        settings=DummySettings(),  # type: ignore[arg-type]
    )


def make_service_with_client() -> tuple[GenerationService, DummyWaveSpeedClient]:
    client = DummyWaveSpeedClient()
    return (
        GenerationService(
            wavespeed_client=client,  # type: ignore[arg-type]
            settings=DummySettings(),  # type: ignore[arg-type]
        ),
        client,
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


def test_build_photo_edit_prompt_uses_required_template_without_changing_user_prompt() -> None:
    service = make_service()
    user_prompt = "замени фон на студию"

    assert service.build_photo_edit_prompt(user_prompt) == PHOTO_EDIT_PROMPT_TEMPLATE.format(
        user_prompt=user_prompt
    )


def test_validate_reference_images_rejects_empty_or_too_many_images() -> None:
    service = make_service()

    with pytest.raises(GenerationError):
        service.validate_reference_images([])

    with pytest.raises(GenerationError):
        service.validate_reference_images(
            ["https://cdn.example/image.png"] * (MAX_REFERENCE_IMAGES + 1)
        )


@pytest.mark.asyncio
async def test_generate_edited_image_uses_edit_model_and_reference_images() -> None:
    service, client = make_service_with_client()

    image_url = await service.generate_edited_image(
        "замени фон на студию",
        [" https://cdn.example/reference.png "],
    )

    assert image_url == "https://cdn.example/image.png"
    assert client.last_prompt == PHOTO_EDIT_PROMPT_TEMPLATE.format(
        user_prompt="замени фон на студию"
    )
    assert client.last_size == "2048*2048"
    assert client.last_images == ["https://cdn.example/reference.png"]
    assert client.last_model_path == "bytedance/seedream-v4/edit"


@pytest.mark.asyncio
async def test_upload_reference_image_returns_provider_url() -> None:
    service = make_service()

    assert (
        await service.upload_reference_image(
            file_bytes=b"image-bytes",
            filename="portrait.jpg",
            content_type="image/jpeg",
        )
        == "https://cdn.example/uploaded.png"
    )
