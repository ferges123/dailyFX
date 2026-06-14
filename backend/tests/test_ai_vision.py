import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services.generation.ai_vision import AIVisionError, AIVisionResult, analyze_image, analyze_images


def _fake_image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (160, 120), color=(128, 64, 32)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_analyze_image_appends_constraint_note():
    settings = MagicMock()
    settings.default_ai_provider = "openai"
    settings.default_ai_model = "gpt-4o-mini"
    settings.encrypted_openai_api_key = b"encrypted-key"

    captured: dict[str, str] = {}

    async def mock_openai(api_key, b64_image, prompt, model):
        captured["prompt"] = prompt
        return AIVisionResult(title="Test", summary="Test Summary")

    with (
        patch("app.services.generation.ai_vision._decrypt_provider_key", return_value="api-key"),
        patch("app.services.generation.ai_vision.reserve_ai_usage", return_value=None),
        patch("app.services.generation.ai_vision._analyze_with_openai", mock_openai),
    ):
        # Test case 1: with context_hint
        asyncio.run(analyze_image(settings, _fake_image_bytes(), context_hint="Some context info"))
        assert "Some context info" in captured["prompt"]
        assert "Do not use placeholders like" in captured["prompt"]

        # Test case 2: without context_hint
        asyncio.run(analyze_image(settings, _fake_image_bytes(), context_hint=None))
        assert "Do not use placeholders like" not in captured["prompt"]


def test_analyze_image_rejects_unsupported_xiaomi_model_for_vision():
    settings = SimpleNamespace(
        default_ai_provider="xiaomi",
        default_ai_model="mimo-v2.5-pro",
        ai_vision_hourly_limit=3,
        encrypted_xiaomi_api_key="secret",
    )

    with (
        patch("app.services.generation.ai_vision._decrypt_provider_key", return_value="secret"),
        patch("app.services.generation.ai_vision.reserve_ai_usage", return_value=None),
        patch(
            "app.services.generation.ai_vision._analyze_with_xiaomi",
            side_effect=AssertionError("unexpected Xiaomi request"),
        ),
    ):
        with pytest.raises(AIVisionError) as exc_info:
            asyncio.run(analyze_image(settings, _fake_image_bytes()))

    message = str(exc_info.value)
    assert "mimo-v2.5" in message
    assert "mimo-v2.5-pro" in message


def test_analyze_images_normalizes_all_images_and_uses_one_provider_request():
    settings = SimpleNamespace(
        default_ai_provider="xiaomi",
        default_ai_model="mimo-v2.5",
        ai_vision_hourly_limit=3,
        encrypted_xiaomi_api_key="secret",
    )
    captured: dict[str, object] = {}

    async def mock_xiaomi(api_key, b64_images, prompt, model):
        captured["api_key"] = api_key
        captured["b64_images"] = b64_images
        captured["prompt"] = prompt
        captured["model"] = model
        return AIVisionResult(title="Ranking", summary='{"selected_index": 1}')

    with (
        patch("app.services.generation.ai_vision._decrypt_provider_key", return_value="secret"),
        patch("app.services.generation.ai_vision.reserve_ai_usage", return_value=None),
        patch(
            "app.services.generation.ai_vision._normalize_image_for_vision",
            side_effect=["img1", "img2", "img3", "img4"],
        ),
        patch("app.services.generation.ai_vision._analyze_images_with_xiaomi", mock_xiaomi),
    ):
        result = asyncio.run(
            analyze_images(
                settings,
                [_fake_image_bytes(), _fake_image_bytes(), _fake_image_bytes(), _fake_image_bytes()],
                prompt="Pick the best image for the Neon Bloom filter.",
            )
        )

    assert result.summary == '{"selected_index": 1}'
    assert captured["b64_images"] == ["img1", "img2", "img3", "img4"]
    assert captured["prompt"] == "Pick the best image for the Neon Bloom filter."
    assert captured["model"] == "mimo-v2.5"


def test_xiaomi_exceptions_handling():
    import httpx

    settings = SimpleNamespace(
        default_ai_provider="xiaomi",
        default_ai_model="mimo-v2.5",
        ai_vision_hourly_limit=3,
        encrypted_xiaomi_api_key="secret",
    )

    # Test TimeoutException
    with (
        patch("app.services.generation.ai_vision._decrypt_provider_key", return_value="secret"),
        patch("app.services.generation.ai_vision.reserve_ai_usage", return_value=None),
        patch("httpx.AsyncClient.post", side_effect=httpx.ReadTimeout("Timeout details")),
        patch("app.services.generation.vision.xiaomi.logger") as mock_logger,
    ):
        with pytest.raises(AIVisionError) as exc_info:
            asyncio.run(analyze_image(settings, _fake_image_bytes()))
        assert "Request timed out" in str(exc_info.value)
        mock_logger.error.assert_called_with("Xiaomi vision error (timeout)", exc_info=True)

    # Test HTTPStatusError
    mock_response = MagicMock()
    mock_response.status_code = 502
    mock_response.request = MagicMock()
    with (
        patch("app.services.generation.ai_vision._decrypt_provider_key", return_value="secret"),
        patch("app.services.generation.ai_vision.reserve_ai_usage", return_value=None),
        patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.HTTPStatusError("Bad Gateway", request=mock_response.request, response=mock_response),
        ),
        patch("app.services.generation.vision.xiaomi.logger") as mock_logger,
    ):
        with pytest.raises(AIVisionError) as exc_info:
            asyncio.run(analyze_image(settings, _fake_image_bytes()))
        assert "HTTP error 502" in str(exc_info.value)
        mock_logger.error.assert_called_with("Xiaomi vision error (HTTP error)", exc_info=True)
