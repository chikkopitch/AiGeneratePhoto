import json

import httpx
import pytest
import respx

from app.services.wavespeed import (
    DEFAULT_IMAGE_SIZE,
    WaveSpeedAPIError,
    WaveSpeedClient,
    WaveSpeedInvalidResponseError,
    WaveSpeedTimeoutError,
)

BASE_URL = "https://api.wavespeed.ai"
CREATE_URL = f"{BASE_URL}/api/v3/bytedance/seedream-v4"
EDIT_URL = f"{BASE_URL}/api/v3/bytedance/seedream-v4/edit"
UPLOAD_URL = f"{BASE_URL}/api/v3/media/upload/binary"
RESULT_URL = f"{BASE_URL}/api/v3/predictions/prediction-1/result"


def prediction_payload(
    *,
    status: str = "created",
    outputs: list[str] | None = None,
    error: str | None = None,
) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "prediction-1",
        "model": "bytedance/seedream-v4",
        "status": status,
        "outputs": outputs or [],
    }
    if error is not None:
        data["error"] = error
    return {
        "code": 200,
        "message": "success",
        "data": data,
    }


@pytest.mark.asyncio
async def test_create_prediction_returns_request_id_with_default_payload(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.post(CREATE_URL).mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )

    async with httpx.AsyncClient() as http_client:
        client = WaveSpeedClient(api_key="test-key", http_client=http_client)
        request_id = await client.create_prediction("cinematic studio portrait")

    assert request_id == "prediction-1"
    assert route.called

    request = route.calls[0].request
    assert request.method == "POST"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {
        "prompt": "cinematic studio portrait",
        "size": DEFAULT_IMAGE_SIZE,
        "enable_base64_output": False,
        "enable_sync_mode": False,
    }


@pytest.mark.asyncio
async def test_create_prediction_can_use_edit_model_and_reference_images(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.post(EDIT_URL).mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )

    async with httpx.AsyncClient() as http_client:
        client = WaveSpeedClient(api_key="test-key", http_client=http_client)
        request_id = await client.create_prediction(
            prompt="replace the background",
            images=["https://cdn.example/reference.png"],
            model_path="bytedance/seedream-v4/edit",
        )

    assert request_id == "prediction-1"
    assert route.called

    request = route.calls[0].request
    assert json.loads(request.content) == {
        "prompt": "replace the background",
        "size": DEFAULT_IMAGE_SIZE,
        "images": ["https://cdn.example/reference.png"],
        "enable_base64_output": False,
        "enable_sync_mode": False,
    }


@pytest.mark.asyncio
async def test_generate_image_polls_until_completed_output(
    respx_mock: respx.MockRouter,
) -> None:
    create_route = respx_mock.post(CREATE_URL).mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )
    result_route = respx_mock.get(RESULT_URL).mock(
        side_effect=[
            httpx.Response(200, json=prediction_payload(status="processing")),
            httpx.Response(
                200,
                json=prediction_payload(
                    status="completed",
                    outputs=["https://cdn.example/final.png"],
                ),
            ),
        ]
    )

    async with httpx.AsyncClient() as http_client:
        client = WaveSpeedClient(
            api_key="test-key",
            poll_interval_seconds=0,
            http_client=http_client,
        )
        image_url = await client.generate_image("cinematic studio portrait")

    assert image_url == "https://cdn.example/final.png"
    assert create_route.call_count == 1
    assert result_route.call_count == 2


@pytest.mark.asyncio
async def test_upload_binary_file_returns_uploaded_url(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.post(UPLOAD_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "message": "success",
                "data": {"download_url": "https://cdn.example/uploaded.png"},
            },
        )
    )

    async with httpx.AsyncClient() as http_client:
        client = WaveSpeedClient(api_key="test-key", http_client=http_client)
        uploaded_url = await client.upload_binary_file(
            file_bytes=b"image-bytes",
            filename="portrait.jpg",
            content_type="image/jpeg",
        )

    assert uploaded_url == "https://cdn.example/uploaded.png"
    assert route.called

    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.headers["Content-Type"].startswith("multipart/form-data")
    assert b'image-bytes' in request.content


@pytest.mark.asyncio
async def test_generate_image_raises_on_failed_status(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(CREATE_URL).mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )
    respx_mock.get(RESULT_URL).mock(
        return_value=httpx.Response(
            200,
            json=prediction_payload(status="failed", error="bad prompt"),
        )
    )

    async with httpx.AsyncClient() as http_client:
        client = WaveSpeedClient(api_key="test-key", http_client=http_client)
        with pytest.raises(WaveSpeedAPIError, match="bad prompt"):
            await client.generate_image("cinematic studio portrait")


@pytest.mark.asyncio
async def test_generate_image_times_out(respx_mock: respx.MockRouter) -> None:
    respx_mock.post(CREATE_URL).mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )
    result_route = respx_mock.get(RESULT_URL).mock(
        return_value=httpx.Response(200, json=prediction_payload(status="processing"))
    )

    async with httpx.AsyncClient() as http_client:
        client = WaveSpeedClient(
            api_key="test-key",
            max_wait_seconds=0,
            poll_interval_seconds=0,
            http_client=http_client,
        )
        with pytest.raises(WaveSpeedTimeoutError):
            await client.generate_image("cinematic studio portrait")

    assert result_route.call_count == 1


@pytest.mark.asyncio
async def test_create_prediction_raises_on_invalid_response(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(CREATE_URL).mock(
        return_value=httpx.Response(200, json={"code": 200, "message": "success"})
    )

    async with httpx.AsyncClient() as http_client:
        client = WaveSpeedClient(api_key="test-key", http_client=http_client)
        with pytest.raises(WaveSpeedInvalidResponseError):
            await client.create_prediction("cinematic studio portrait")
