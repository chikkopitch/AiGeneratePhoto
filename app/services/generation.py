import logging

from app.config import Settings
from app.services.wavespeed import (
    WavespeedAPIError,
    WavespeedClient,
    WavespeedError,
    WavespeedInvalidResponseError,
    WavespeedTimeoutError,
)

logger = logging.getLogger(__name__)

MIN_PROMPT_LENGTH = 10
MAX_PROMPT_LENGTH = 1500
PHOTO_PROMPT_TEMPLATE = (
    "Professional AI photoshoot, realistic portrait photography, {user_prompt}, "
    "cinematic lighting, high detail, natural skin texture, sharp focus, 85mm lens, "
    "soft background, premium editorial style"
)
FORBIDDEN_KEYWORDS = frozenset(
    {
        "child sexual",
        "csam",
        "explosive device",
        "how to make a bomb",
        "kill someone",
        "murder",
        "наркотики",
        "порнография с детьми",
        "самодельная бомба",
        "убить человека",
    }
)


class GenerationError(Exception):
    def __init__(
        self,
        message: str,
        request_id: str | None = None,
        status: str | None = None,
    ) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.status = status


class PromptValidationError(GenerationError):
    pass


class GenerationProviderError(GenerationError):
    pass


class GenerationTimeoutError(GenerationError):
    pass


class GenerationInvalidResponseError(GenerationProviderError):
    pass


class GenerationService:
    def __init__(self, wavespeed_client: WavespeedClient, settings: Settings) -> None:
        self._wavespeed_client = wavespeed_client
        self._settings = settings

    async def generate_image(self, prompt: str) -> str:
        """Validate and improve a user prompt, then generate an image URL."""

        clean_prompt = self.validate_prompt(prompt)
        photo_prompt = self.build_photo_prompt(clean_prompt)

        logger.info("Starting image generation", extra={"status": "started"})
        try:
            image_url = await self._wavespeed_client.generate_image(
                prompt=photo_prompt,
                size=self._settings.default_image_size,
            )
        except WavespeedTimeoutError as exc:
            logger.exception(
                "Image generation timed out",
                extra={
                    "request_id": exc.request_id or "-",
                    "status": exc.status or "timeout",
                    "error_type": type(exc).__name__,
                },
            )
            raise GenerationTimeoutError(
                "Image generation timed out",
                request_id=exc.request_id,
                status=exc.status,
            ) from exc
        except WavespeedInvalidResponseError as exc:
            logger.exception(
                "Image generation provider returned invalid response",
                extra={
                    "request_id": exc.request_id or "-",
                    "status": exc.status or "invalid_response",
                    "error_type": type(exc).__name__,
                },
            )
            raise GenerationInvalidResponseError(
                "Image generation provider returned invalid response",
                request_id=exc.request_id,
                status=exc.status,
            ) from exc
        except WavespeedAPIError as exc:
            logger.exception(
                "Image generation provider API error",
                extra={
                    "request_id": exc.request_id or "-",
                    "status": exc.status or "api_error",
                    "error_type": type(exc).__name__,
                },
            )
            raise GenerationProviderError(
                "Image generation provider API error",
                request_id=exc.request_id,
                status=exc.status,
            ) from exc
        except WavespeedError as exc:
            logger.exception(
                "Image generation provider error",
                extra={
                    "request_id": exc.request_id or "-",
                    "status": exc.status or "provider_error",
                    "error_type": type(exc).__name__,
                },
            )
            raise GenerationProviderError(
                "Image generation provider error",
                request_id=exc.request_id,
                status=exc.status,
            ) from exc
        except Exception as exc:
            logger.exception(
                "Image generation failed",
                extra={"status": "failed", "error_type": type(exc).__name__},
            )
            raise GenerationError("Image generation failed") from exc

        logger.info("Image generation completed", extra={"status": "completed"})
        return image_url

    def validate_prompt(self, prompt: str) -> str:
        """Validate a user prompt and return a stripped prompt."""

        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise PromptValidationError("Prompt is empty")
        if len(clean_prompt) < MIN_PROMPT_LENGTH:
            raise PromptValidationError(
                f"Prompt must contain at least {MIN_PROMPT_LENGTH} characters"
            )
        if len(clean_prompt) > MAX_PROMPT_LENGTH:
            raise PromptValidationError(
                f"Prompt must contain no more than {MAX_PROMPT_LENGTH} characters"
            )

        normalized_prompt = clean_prompt.casefold()
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword.casefold() in normalized_prompt:
                raise PromptValidationError("Prompt contains forbidden content")

        return clean_prompt

    def build_photo_prompt(self, user_prompt: str) -> str:
        """Build a photo-oriented AI prompt without changing the user's meaning."""

        clean_prompt = user_prompt.strip()
        return PHOTO_PROMPT_TEMPLATE.format(user_prompt=clean_prompt)
