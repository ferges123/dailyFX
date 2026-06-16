import asyncio
import base64
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from _contract_helpers import configure_contract_test_db
from PIL import Image

from app.database import SessionLocal, init_db
from app.models.ai_usage import AIUsageEventModel
from app.services.generation.ai_budget import AIUsageLimitExceededError, count_recent_usage, reserve_ai_usage
from app.services.generation.ai_image import AIImageError, AIImageResult, encode_image_for_provider, generate_ai_image
from app.services.generation.ai_vision import AIVisionResult, analyze_image

test_db = configure_contract_test_db("ai_budget")


def _png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (8, 8), color=(120, 80, 40)).save(buf, format="PNG")
    return buf.getvalue()


def _clear_usage_events() -> None:
    db = SessionLocal()
    try:
        db.query(AIUsageEventModel).delete()
        db.commit()
    finally:
        db.close()


class _FakeResponse:
    def __init__(
        self, *, status_code: int = 200, json_body: object | None = None, content: bytes = b"", text: str = ""
    ):
        self.status_code = status_code
        self._json_body = json_body
        self.content = content
        self.text = text
        self.headers = {
            "content-type": "application/json" if json_body is not None else "application/octet-stream",
            "content-length": str(len(content or text.encode("utf-8"))),
        }

    def json(self):
        if self._json_body is None:
            raise ValueError("not json")
        return self._json_body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "boom", request=httpx.Request("POST", "https://example.test"), response=httpx.Response(self.status_code)
            )


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.requests: list[dict[str, object]] = []
        self.next_post_response = _FakeResponse()
        self.next_get_response = _FakeResponse(content=b"")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None, files=None, data=None):
        self.requests.append(
            {"method": "POST", "url": url, "headers": headers, "json": json, "files": files, "data": data}
        )
        return self.next_post_response

    async def get(self, url, headers=None):
        self.requests.append({"method": "GET", "url": url, "headers": headers})
        return self.next_get_response


def test_ai_budget_counts_vision_and_image_separately():
    init_db()
    _clear_usage_events()
    db = SessionLocal()
    try:
        reserve_ai_usage("vision", limit=2, provider="openai", model="gpt-4o-mini", now=datetime.now(timezone.utc))
        reserve_ai_usage("image", limit=1, provider="openai", model="gpt-image-1", now=datetime.now(timezone.utc))

        assert count_recent_usage(db, "vision") == 1
        assert count_recent_usage(db, "image") == 1
    finally:
        db.close()


def test_ai_budget_blocks_after_hourly_limit():
    init_db()
    _clear_usage_events()
    reserve_ai_usage("image", limit=1, provider="openai", model="gpt-image-1", now=datetime.now(timezone.utc))

    with pytest.raises(AIUsageLimitExceededError):
        reserve_ai_usage("image", limit=1, provider="openai", model="gpt-image-1", now=datetime.now(timezone.utc))


def test_analyze_image_reserves_vision_budget_before_request():
    init_db()
    settings = SimpleNamespace(
        default_ai_provider="openai",
        default_ai_model="gpt-4o-mini",
        ai_vision_hourly_limit=3,
        encrypted_openai_api_key="secret",
    )
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def fake_analyze(*args, **kwargs):
        return AIVisionResult(
            title="Vision", summary="Summary", tags=["one"], token_count=1, provider="openai", model="gpt-4o-mini"
        )

    with (
        patch("app.services.generation.ai_vision._decrypt_provider_key", return_value="secret"),
        patch(
            "app.services.generation.ai_vision.reserve_ai_usage",
            side_effect=lambda *args, **kwargs: calls.append((args, kwargs)),
        ),
        patch("app.services.generation.ai_vision._analyze_with_openai", side_effect=fake_analyze),
    ):
        result = asyncio.run(analyze_image(settings, _png_bytes()))

    assert calls[0][0] == ("vision",)
    assert calls[0][1]["limit"] == 3
    assert result.title == "Vision"


def test_analyze_image_supports_xiaomi_models():
    init_db()
    settings = SimpleNamespace(
        default_ai_provider="xiaomi",
        default_ai_model="mimo-v2.5",
        ai_vision_hourly_limit=3,
        encrypted_xiaomi_api_key="secret",
    )
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def fake_analyze(*args, **kwargs):
        return AIVisionResult(
            title="Vision", summary="Summary", tags=["one"], token_count=1, provider="xiaomi", model="mimo-v2.5"
        )

    with (
        patch("app.services.generation.ai_vision._decrypt_provider_key", return_value="secret"),
        patch(
            "app.services.generation.ai_vision.reserve_ai_usage",
            side_effect=lambda *args, **kwargs: calls.append((args, kwargs)),
        ),
        patch("app.services.generation.ai_vision._analyze_with_xiaomi", side_effect=fake_analyze),
    ):
        result = asyncio.run(analyze_image(settings, _png_bytes()))

    assert calls[0][0] == ("vision",)
    assert calls[0][1]["limit"] == 3
    assert result.provider == "xiaomi"
    assert result.model == "mimo-v2.5"


def test_analyze_image_supports_local_models(monkeypatch):
    init_db()
    settings = SimpleNamespace(
        default_ai_provider="local",
        default_ai_model="qwen2.5-vl",
        ai_vision_hourly_limit=3,
        local_ai_base_url="http://local-ai.example.test/v1",
        encrypted_local_ai_api_key="secret",
    )
    fake_client = _FakeAsyncClient()
    fake_client.next_post_response = _FakeResponse(
        json_body={
            "choices": [
                {
                    "message": {
                        "content": '{"title":"Local Vision","summary":"Local summary","tags":["one","two"]}',
                    }
                }
            ],
            "usage": {"total_tokens": 7},
        }
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    with (
        patch("app.services.generation.vision.base.get_local_ai_api_key", return_value="secret"),
        patch("app.services.generation.ai_vision.reserve_ai_usage", return_value=None),
    ):
        result = asyncio.run(analyze_image(settings, _png_bytes()))

    assert result.provider == "local"
    assert result.model == "qwen2.5-vl"
    assert result.title == "Local Vision"
    assert result.tags == ["one", "two"]
    assert fake_client.requests[0]["url"] == "http://local-ai.example.test/v1/chat/completions"


def test_generate_ai_image_reserves_image_budget_before_request():
    init_db()
    settings = SimpleNamespace(
        ai_image_provider="openai",
        ai_image_model="gpt-image-1",
        ai_image_hourly_limit=4,
        encrypted_openai_api_key="secret",
    )
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def fake_generate(*args, **kwargs):
        return b"image-bytes"

    with (
        patch("app.services.generation.ai_image._decrypt_provider_key", return_value="secret"),
        patch(
            "app.services.generation.ai_image.reserve_ai_usage",
            side_effect=lambda *args, **kwargs: calls.append((args, kwargs)),
        ),
        patch("app.services.generation.ai_image._generate_with_openai", side_effect=fake_generate),
    ):
        result = asyncio.run(generate_ai_image(settings, _png_bytes(), "prompt"))

    assert calls[0][0] == ("image",)
    assert calls[0][1]["limit"] == 4
    assert isinstance(result, AIImageResult)
    assert result.image_bytes == b"image-bytes"


def test_generate_ai_image_supports_local_models(monkeypatch):
    init_db()
    settings = SimpleNamespace(
        ai_image_provider="local",
        ai_image_model="qwen-image",
        ai_image_hourly_limit=4,
        local_ai_base_url="http://local-ai.example.test/v1",
        encrypted_local_ai_api_key="secret",
    )
    fake_client = _FakeAsyncClient()
    fake_client.next_post_response = _FakeResponse(
        json_body={"data": [{"b64_json": base64.b64encode(_png_bytes()).decode("ascii")}]}
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    with (
        patch("app.services.generation.ai_image.get_local_ai_api_key", return_value="secret"),
        patch("app.services.generation.ai_image.reserve_ai_usage", return_value=None),
    ):
        result = asyncio.run(generate_ai_image(settings, _png_bytes(), "prompt"))

    assert result.provider == "local"
    assert result.model == "qwen-image"
    assert result.image_bytes == _png_bytes()
    assert fake_client.requests[0]["url"] == "http://local-ai.example.test/v1/images/edits"
    assert fake_client.requests[0]["files"][0][0] == "image"
    assert fake_client.requests[0]["files"][0][1][0] == "source.png"
    assert fake_client.requests[0]["data"]["model"] == "qwen-image"
    assert fake_client.requests[0]["data"]["prompt"] == "prompt"


def test_generate_ai_image_uses_byteplus_images_endpoint(monkeypatch):
    init_db()
    settings = SimpleNamespace(
        ai_image_provider="byteplus",
        ai_image_model="seededit-3-0-i2i-250628",
        ai_image_hourly_limit=4,
        encrypted_byteplus_api_key="secret",
    )
    fake_client = _FakeAsyncClient()
    fake_client.next_post_response = _FakeResponse(json_body={"data": [{"url": "https://cdn.example.test/result.png"}]})
    fake_client.next_get_response = _FakeResponse(content=_png_bytes())
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    with (
        patch("app.services.generation.ai_image._decrypt_provider_key", return_value="secret"),
        patch("app.services.generation.ai_image.reserve_ai_usage", return_value=None),
    ):
        result = asyncio.run(generate_ai_image(settings, _png_bytes(), "make it playful"))

    assert result.provider == "byteplus"
    assert result.model == "seededit-3-0-i2i-250628"
    assert result.image_bytes == _png_bytes()
    assert fake_client.requests[0]["url"] == "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"
    assert fake_client.requests[0]["json"]["prompt"] == "make it playful"
    assert fake_client.requests[0]["json"]["image"].startswith("data:image/jpeg;base64,")
    assert fake_client.requests[0]["json"]["size"] == "adaptive"
    assert "messages" not in fake_client.requests[0]["json"]


def test_encode_image_for_provider_uses_expected_format():
    raw = _png_bytes()

    openai_bytes, openai_mime = encode_image_for_provider(raw, "openai")
    gemini_bytes, gemini_mime = encode_image_for_provider(raw, "gemini")
    openrouter_bytes, openrouter_mime = encode_image_for_provider(raw, "openrouter")
    byteplus_bytes, byteplus_mime = encode_image_for_provider(raw, "byteplus")

    assert openai_mime == "image/png"
    assert gemini_mime == "image/png"
    assert openrouter_mime == "image/jpeg"
    assert byteplus_mime == "image/jpeg"
    assert openai_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert gemini_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert openrouter_bytes.startswith(b"\xff\xd8")
    assert byteplus_bytes.startswith(b"\xff\xd8")


def test_generate_ai_image_logs_byteplus_error_body(monkeypatch):
    init_db()
    settings = SimpleNamespace(
        ai_image_provider="byteplus",
        ai_image_model="seededit-3-0-i2i-250628",
        ai_image_hourly_limit=4,
        encrypted_byteplus_api_key="secret",
    )
    fake_client = _FakeAsyncClient()
    fake_client.next_post_response = _FakeResponse(
        status_code=500,
        json_body={"error": {"message": "BytePlus internal failure", "trace": "very long details"}},
        text='{"error":{"message":"BytePlus internal failure","trace":"very long details"}}',
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    with (
        patch("app.services.generation.ai_image._decrypt_provider_key", return_value="secret"),
        patch("app.services.generation.ai_image.reserve_ai_usage", return_value=None),
        patch("app.services.generation.ai_image.debug_log") as debug_mock,
    ):
        try:
            asyncio.run(generate_ai_image(settings, _png_bytes(), "make it playful"))
        except Exception as exc:  # noqa: BLE001
            exc_info = exc
        else:
            raise AssertionError("Expected BytePlus image generation to fail")

    assert "BytePlus image generation failed" in str(exc_info)
    error_calls = [
        call for call in debug_mock.call_args_list if call.args and call.args[0] == "BytePlus image error response body"
    ]
    assert error_calls
    assert "BytePlus internal failure" in error_calls[0].kwargs["body"]


def test_generate_ai_image_logs_byteplus_error_hint(monkeypatch):
    init_db()
    settings = SimpleNamespace(
        ai_image_provider="byteplus",
        ai_image_model="seededit-3-0-i2i-250628",
        ai_image_hourly_limit=4,
        encrypted_byteplus_api_key="secret",
    )
    fake_client = _FakeAsyncClient()
    fake_client.next_post_response = _FakeResponse(
        status_code=403,
        json_body={"error": {"message": "API key rejected by BytePlus"}},
        text='{"error":{"message":"API key rejected by BytePlus"}}',
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    with (
        patch("app.services.generation.ai_image._decrypt_provider_key", return_value="secret"),
        patch("app.services.generation.ai_image.reserve_ai_usage", return_value=None),
        patch("app.services.generation.ai_image.debug_log") as debug_mock,
    ):
        try:
            asyncio.run(generate_ai_image(settings, _png_bytes(), "make it playful"))
        except Exception:  # noqa: BLE001
            pass
        else:
            raise AssertionError("Expected BytePlus image generation to fail")

    hint_calls = [
        call for call in debug_mock.call_args_list if call.args and call.args[0] == "BytePlus image error hint"
    ]
    assert hint_calls
    assert "API key" in hint_calls[0].kwargs["hint"]


def test_generate_ai_image_byteplus_error_message(monkeypatch):
    init_db()
    settings = SimpleNamespace(
        ai_image_provider="byteplus",
        ai_image_model="seededit-3-0-i2i-250628",
        ai_image_hourly_limit=4,
        encrypted_byteplus_api_key="secret",
    )
    fake_client = _FakeAsyncClient()
    fake_client.next_post_response = _FakeResponse(
        status_code=404,
        json_body={"error": {"message": "Model seededit-3-0-i2i-250628 not found"}},
        text='{"error":{"message":"Model seededit-3-0-i2i-250628 not found"}}',
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    with (
        patch("app.services.generation.ai_image._decrypt_provider_key", return_value="secret"),
        patch("app.services.generation.ai_image.reserve_ai_usage", return_value=None),
    ):
        try:
            asyncio.run(generate_ai_image(settings, _png_bytes(), "make it playful"))
        except AIImageError as exc:
            exc_info = exc
        else:
            raise AssertionError("Expected BytePlus image generation to fail")

    assert (
        "BytePlus image generation failed (HTTP 404): Model seededit-3-0-i2i-250628 not found. Hint: Check the BytePlus model/endpoint ID in settings."
        in str(exc_info)
    )


def test_crop_to_largest_face():
    from io import BytesIO

    from PIL import Image

    from app.services.generation.ai_image import _crop_to_largest_face

    # Create a 200x400 vertical red image
    img = Image.new("RGB", (200, 400), (255, 0, 0))
    # Draw a green face box at (50, 50) to (150, 150)
    for x in range(50, 150):
        for y in range(50, 150):
            img.putpixel((x, y), (0, 255, 0))

    out = BytesIO()
    img.save(out, format="PNG")
    img_bytes = out.getvalue()

    # Large face near the top (bounding box in pixels)
    faces = [
        {
            "bounding_box_x1": 50.0,
            "bounding_box_y1": 50.0,
            "bounding_box_x2": 150.0,
            "bounding_box_y2": 150.0,
        }
    ]

    cropped_bytes = _crop_to_largest_face(img_bytes, faces)
    cropped_img = Image.open(BytesIO(cropped_bytes))

    assert cropped_img.size == (200, 200)
    # The crop box should center on cy = 100, which means top = 100 - 100 = 0.
    # So the green square should be fully contained at the top of the cropped image.
    assert cropped_img.getpixel((50, 50)) == (0, 255, 0)


def test_generate_ai_image_openai_crops_image(monkeypatch):
    from app.services.generation.ai_image import generate_ai_image

    init_db()
    settings = SimpleNamespace(
        ai_image_provider="openai",
        ai_image_model="dall-e-2",
        ai_image_hourly_limit=4,
        encrypted_openai_api_key="secret",
    )

    fake_client = _FakeAsyncClient()
    # Mock Response returning base64
    fake_client.next_post_response = _FakeResponse(json_body={"data": [{"b64_json": "ZmFrZV9wbmdfYnl0ZXM="}]})
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    # 200x400 source image
    from io import BytesIO

    from PIL import Image

    img = Image.new("RGB", (200, 400), (255, 0, 0))
    out = BytesIO()
    img.save(out, format="PNG")
    raw_image_bytes = out.getvalue()

    faces = [
        {
            "bounding_box_x1": 50.0,
            "bounding_box_y1": 50.0,
            "bounding_box_x2": 150.0,
            "bounding_box_y2": 150.0,
        }
    ]

    with (
        patch("app.services.generation.ai_image._decrypt_provider_key", return_value="secret"),
        patch("app.services.generation.ai_image.reserve_ai_usage", return_value=None),
    ):
        result = asyncio.run(generate_ai_image(settings, raw_image_bytes, "make it playful", faces=faces))

    assert result.provider == "openai"
    # Verify the image sent in the files parameter is square (200x200)
    sent_file = fake_client.requests[0]["files"][0][1][1]
    sent_img = Image.open(BytesIO(sent_file))
    assert sent_img.size == (200, 200)
