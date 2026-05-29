"""Async client for the WaveSpeed image generation API."""

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.wavespeed.ai"
DEFAULT_MODEL_PATH = "bytedance/seedream-v4"
DEFAULT_IMAGE_SIZE = "2048*2048"
DEFAULT_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_MAX_WAIT_SECONDS = 120.0

logger = logging.getLogger(__name__)


class WaveSpeedError(Exception):
    """Base exception for WaveSpeed client errors."""

    def __init__(
        self,
        message: str,
        request_id: str | None = None,
        status: str | None = None,
    ) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.status = status


class WaveSpeedAPIError(WaveSpeedError):
    """Raised when WaveSpeed returns an HTTP/API error or malformed response."""


class WaveSpeedInvalidResponseError(WaveSpeedAPIError):
    """Raised when WaveSpeed returns a response with an unexpected shape."""


class WaveSpeedTimeoutError(WaveSpeedError, TimeoutError):
    """Raised when WaveSpeed generation does not finish before the timeout."""


@dataclass(frozen=True)
class WaveSpeedPrediction:
    """Normalized WaveSpeed prediction payload used by the service layer."""

    request_id: str
    model: str | None
    status: str
    outputs: list[str]
    error: str | None = None

    @property
    def first_output(self) -> str | None:
        """Return the first generated output URL, if WaveSpeed returned one."""

        return self.outputs[0] if self.outputs else None


class WaveSpeedClient:
    """Asynchronous client for creating and polling WaveSpeed predictions.

    The client sends requests with Bearer authentication, never logs the API key,
    and exposes the MVP-friendly `generate_image` method as well as lower-level
    methods for creating and reading predictions.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model_path: str = DEFAULT_MODEL_PATH,
        request_timeout_seconds: float = 60.0,
        timeout_seconds: float | None = None,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model_path = model_path.strip("/")
        self._poll_interval_seconds = poll_interval_seconds
        self._max_wait_seconds = max_wait_seconds
        self._owns_http_client = http_client is None
        request_timeout = timeout_seconds if timeout_seconds is not None else request_timeout_seconds
        self._http_client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(request_timeout),
        )

    async def create_prediction(
        self,
        prompt: str,
        size: str = DEFAULT_IMAGE_SIZE,
        images: Iterable[str] | None = None,
        model_path: str | None = None,
    ) -> str:
        """Create an image generation prediction and return its request id."""

        payload = {
            "prompt": prompt,
            "size": size,
            "enable_base64_output": False,
            "enable_sync_mode": False,
        }
        if images is not None:
            payload["images"] = list(images)

        response_payload = await self._request(
            "POST",
            f"/api/v3/{self._prediction_model_path(model_path)}",
            json=payload,
        )
        request_id = self._extract_request_id(response_payload)
        logger.info("WaveSpeed prediction created", extra={"request_id": request_id})
        return request_id

    async def get_prediction_result(self, request_id: str) -> dict[str, Any]:
        """Fetch the raw WaveSpeed prediction result payload by request id."""

        try:
            response_payload = await self._request(
                "GET",
                f"/api/v3/predictions/{request_id}/result",
            )
        except WaveSpeedError as exc:
            if exc.request_id is None:
                exc.request_id = request_id
            raise
        logger.info("WaveSpeed prediction result fetched", extra={"request_id": request_id})
        return response_payload

    async def generate_image(
        self,
        prompt: str,
        size: str = DEFAULT_IMAGE_SIZE,
        images: Iterable[str] | None = None,
        model_path: str | None = None,
    ) -> str:
        """Generate an image and return the first output URL.

        The method creates a prediction, polls every two seconds by default, and
        raises `WaveSpeedAPIError` for failed/error statuses or
        `WaveSpeedTimeoutError` when the 120-second timeout is reached.
        """

        request_id = await self.create_prediction(
            prompt=prompt,
            size=size,
            images=images,
            model_path=model_path,
        )
        deadline = monotonic() + self._max_wait_seconds

        while True:
            response_payload = await self.get_prediction_result(request_id)
            prediction = self._parse_prediction(response_payload)
            status = prediction.status.lower()

            if status == "completed":
                if prediction.first_output is None:
                    raise WaveSpeedInvalidResponseError(
                        "WaveSpeed generation completed without output URL",
                        request_id=request_id,
                        status=status,
                    )
                logger.info("WaveSpeed prediction completed", extra={"request_id": request_id})
                return prediction.first_output

            if status in {"failed", "error"}:
                message = prediction.error or "WaveSpeed generation failed"
                raise WaveSpeedAPIError(
                    f"WaveSpeed generation failed: {message}",
                    request_id=request_id,
                    status=status,
                )

            remaining_seconds = deadline - monotonic()
            if remaining_seconds <= 0:
                raise WaveSpeedTimeoutError(
                    f"WaveSpeed generation timed out after {int(self._max_wait_seconds)} seconds",
                    request_id=request_id,
                    status="timeout",
                )

            await asyncio.sleep(min(self._poll_interval_seconds, remaining_seconds))

    async def upload_binary_file(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a binary media file and return the WaveSpeed-hosted URL."""

        response_payload = await self._request(
            "POST",
            "/api/v3/media/upload/binary",
            files={"file": (filename, file_bytes, content_type)},
        )
        return self._extract_uploaded_url(response_payload)

    async def submit_generation(
        self,
        prompt: str,
        size: str,
        enable_sync_mode: bool = False,
    ) -> WaveSpeedPrediction:
        """Compatibility wrapper that creates a prediction and returns normalized data."""

        payload = {
            "prompt": prompt,
            "size": size,
            "enable_base64_output": False,
            "enable_sync_mode": enable_sync_mode,
        }
        response_payload = await self._request(
            "POST",
            f"/api/v3/{self._model_path}",
            json=payload,
        )
        prediction = self._parse_prediction(response_payload)
        logger.info("WaveSpeed prediction created", extra={"request_id": prediction.request_id})
        return prediction

    async def get_result(self, request_id: str) -> WaveSpeedPrediction:
        """Compatibility wrapper that fetches and normalizes a prediction result."""

        return self._parse_prediction(await self.get_prediction_result(request_id))

    async def wait_for_result(
        self,
        request_id: str,
        poll_interval_seconds: float,
        max_attempts: int,
    ) -> WaveSpeedPrediction:
        """Compatibility wrapper that polls by attempt count and returns normalized data."""

        for attempt in range(max_attempts):
            prediction = await self.get_result(request_id)
            status = prediction.status.lower()

            if status == "completed":
                if prediction.first_output is None:
                    raise WaveSpeedInvalidResponseError(
                        "WaveSpeed generation completed without output URL",
                        request_id=request_id,
                        status=status,
                    )
                return prediction

            if status in {"failed", "error"}:
                raise WaveSpeedAPIError(
                    prediction.error or "WaveSpeed generation failed",
                    request_id=request_id,
                    status=status,
                )

            if attempt < max_attempts - 1 and poll_interval_seconds > 0:
                await asyncio.sleep(poll_interval_seconds)

        raise WaveSpeedTimeoutError(
            "WaveSpeed generation timed out",
            request_id=request_id,
            status="timeout",
        )

    async def close(self) -> None:
        """Close the internally owned HTTP client."""

        if self._owns_http_client:
            await self._http_client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        extra_headers = kwargs.pop("headers", None)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        if "files" not in kwargs:
            headers["Content-Type"] = "application/json"
        if extra_headers is not None:
            headers.update(extra_headers)

        try:
            response = await self._http_client.request(
                method,
                self._absolute_url(path),
                headers=headers,
                **kwargs,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            response_text = self._sanitize_message(exc.response.text[:500])
            raise WaveSpeedAPIError(
                f"WaveSpeed HTTP {exc.response.status_code}: {response_text}",
                status=str(exc.response.status_code),
            ) from exc
        except httpx.HTTPError as exc:
            raise WaveSpeedAPIError(f"WaveSpeed request failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise WaveSpeedInvalidResponseError("WaveSpeed returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise WaveSpeedInvalidResponseError("WaveSpeed returned non-object JSON")

        code = payload.get("code")
        if self._is_error_code(code):
            message = self._sanitize_message(str(payload.get("message") or "WaveSpeed API error"))
            raise WaveSpeedAPIError(message)

        return payload

    def _absolute_url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    def _prediction_model_path(self, model_path: str | None) -> str:
        return (model_path or self._model_path).strip("/")

    def _parse_prediction(self, payload: dict[str, Any]) -> WaveSpeedPrediction:
        data = self._extract_data(payload)
        request_id = self._extract_request_id(payload)
        return WaveSpeedPrediction(
            request_id=request_id,
            model=str(data["model"]) if data.get("model") is not None else None,
            status=str(data.get("status") or "created").strip(),
            outputs=self._normalize_outputs(data.get("outputs")),
            error=str(data["error"]) if data.get("error") else None,
        )

    def _extract_request_id(self, payload: dict[str, Any]) -> str:
        data = self._extract_data(payload)
        request_id = data.get("id")
        if not request_id:
            raise WaveSpeedInvalidResponseError("WaveSpeed response does not contain prediction id")
        return str(request_id)

    def _extract_uploaded_url(self, payload: dict[str, Any]) -> str:
        data = self._extract_data(payload)
        uploaded_url = data.get("download_url") or data.get("url")
        if not uploaded_url:
            raise WaveSpeedInvalidResponseError("WaveSpeed upload response does not contain file URL")
        return str(uploaded_url)

    @staticmethod
    def _extract_data(payload: dict[str, Any]) -> dict[str, Any]:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise WaveSpeedInvalidResponseError("WaveSpeed response does not contain data object")
        return data

    @staticmethod
    def _normalize_outputs(outputs: Any) -> list[str]:
        if outputs is None:
            return []
        if isinstance(outputs, str):
            return [outputs] if outputs else []
        if isinstance(outputs, Iterable):
            return [str(output) for output in outputs if output]
        return []

    @staticmethod
    def _is_error_code(code: Any) -> bool:
        if code is None:
            return False
        try:
            return int(code) >= 400
        except (TypeError, ValueError):
            return False

    def _sanitize_message(self, message: str) -> str:
        return message.replace(self._api_key, "[redacted]")


# Backward-compatible names used by the rest of the project.
WavespeedError = WaveSpeedError
WavespeedAPIError = WaveSpeedAPIError
WavespeedInvalidResponseError = WaveSpeedInvalidResponseError
WavespeedTimeoutError = WaveSpeedTimeoutError
WavespeedPrediction = WaveSpeedPrediction
WavespeedClient = WaveSpeedClient
