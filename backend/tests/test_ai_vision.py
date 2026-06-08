import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services.generation.ai_vision import AIVisionError, AIVisionResult, analyze_image

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

    with patch("app.services.generation.ai_vision._decrypt_provider_key", return_value="api-key"), \
         patch("app.services.generation.ai_vision.reserve_ai_usage", return_value=None), \
         patch("app.services.generation.ai_vision._analyze_with_openai", mock_openai):
        
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
