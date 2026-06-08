import asyncio
import os
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

os.environ["APP_ENV"] = "development"
os.environ["APP_SECRET_KEY"] = "test-api-secret"
test_db = Path("/tmp/immich_ai_creator_test_generation_modules.db")
test_db.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"

from app.models.ai_effect import AIEffectModel
from app.services.generation.ai_effects_builder import build_ai_module
from app.services.generation.ai_image import generate_ai_image
from app.services.generation.modules.cyanotype import CyanotypeModule
from app.services.generation.modules.paper_cutout import PaperCutoutModule
from app.services.generation.modules.polaroid import PolaroidModule
from app.services.generation.modules.prism_split import PrismSplitModule


def _create_mock_ai_module(module_name: str) -> object:
    return build_ai_module(
        AIEffectModel(
            id=module_name,
            title=module_name.replace("_", " ").title(),
            description=f"Description of {module_name}",
            positive_prompt=f"Transform photo into {module_name}",
            negative_prompt="low quality",
            custom_prompt_placeholder="custom prompt",
            enabled=True,
            source="builtin",
        )
    )


def _fake_asset(asset_id: str = "asset-1", filename: str = "photo.jpg"):
    asset = MagicMock()
    asset.id = asset_id
    asset.original_file_name = filename
    asset.created_at = "2024-06-15T10:30:00.000Z"
    return asset


def _fake_image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (160, 120), color=(128, 64, 32)).save(buffer, format="PNG")
    return buffer.getvalue()


def _assert_png(result):
    assert result.image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(BytesIO(result.image_bytes))
    image.verify()


def test_new_art_modules_generate_png():
    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=_fake_image_bytes())
    client.get_asset_exif = AsyncMock(return_value={"city": "Warsaw"})
    settings = MagicMock()
    asset = _fake_asset()
    modules = [
        (CyanotypeModule(), "cyanotype"),
        (PolaroidModule(), "polaroid"),
        (PrismSplitModule(), "prism_split"),
        (PaperCutoutModule(), "paper_cutout"),
    ]

    for module, expected_type in modules:
        result = asyncio.run(module.run([asset], {}, client, settings))
        assert result.generation_type == expected_type
        assert result.source_asset_ids == [asset.id]
        _assert_png(result)


def test_ai_modules_use_stubbed_ai_helper():
    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=_fake_image_bytes())
    client.get_asset_thumbnail = AsyncMock(return_value=(_fake_image_bytes(), "image/png"))
    settings = MagicMock(default_ai_provider="openai")
    asset = _fake_asset()
    ai_result = SimpleNamespace(image_bytes=_fake_image_bytes(), provider="openai", model="gpt-image-1")

    with patch("app.services.generation.modules.ai_style_base.generate_ai_image", AsyncMock(return_value=ai_result)):
        caricature = asyncio.run(_create_mock_ai_module("ai_caricature").run([asset], {}, client, settings))
        anime = asyncio.run(_create_mock_ai_module("ai_anime").run([asset], {}, client, settings))
        toy = asyncio.run(_create_mock_ai_module("ai_cinematic_3d_toy").run([asset], {}, client, settings))
        figure = asyncio.run(_create_mock_ai_module("ai_collectible_figure").run([asset], {}, client, settings))
        fantasy = asyncio.run(_create_mock_ai_module("ai_fantasy_hero").run([asset], {}, client, settings))
        fashion = asyncio.run(_create_mock_ai_module("ai_high_fashion_editorial").run([asset], {}, client, settings))
        brick = asyncio.run(_create_mock_ai_module("ai_brick_built_figure").run([asset], {}, client, settings))
        cartoon = asyncio.run(_create_mock_ai_module("ai_yellow_cartoon_sitcom").run([asset], {}, client, settings))

    assert caricature.generation_type == "ai_caricature"
    assert caricature.provider == "openai"
    assert caricature.model == "gpt-image-1"
    assert caricature.source_asset_ids == [asset.id]
    _assert_png(caricature)

    assert anime.generation_type == "ai_anime"
    assert anime.provider == "openai"
    assert anime.model == "gpt-image-1"
    assert anime.source_asset_ids == [asset.id]
    _assert_png(anime)

    for result, expected_type in [
        (toy, "ai_cinematic_3d_toy"),
        (figure, "ai_collectible_figure"),
        (fantasy, "ai_fantasy_hero"),
        (fashion, "ai_high_fashion_editorial"),
        (brick, "ai_brick_built_figure"),
        (cartoon, "ai_yellow_cartoon_sitcom"),
    ]:
        assert result.generation_type == expected_type
        assert result.provider == "openai"
        assert result.model == "gpt-image-1"
        assert result.source_asset_ids == [asset.id]
        _assert_png(result)


def test_ai_modules_share_custom_prompt_schema():
    modules = [
        _create_mock_ai_module("ai_anime"),
        _create_mock_ai_module("ai_caricature"),
        _create_mock_ai_module("ai_comic_book"),
        _create_mock_ai_module("ai_claymation"),
        _create_mock_ai_module("ai_cyberpunk"),
        _create_mock_ai_module("ai_cinematic_3d_toy"),
        _create_mock_ai_module("ai_collectible_figure"),
        _create_mock_ai_module("ai_fantasy_hero"),
        _create_mock_ai_module("ai_high_fashion_editorial"),
        _create_mock_ai_module("ai_brick_built_figure"),
        _create_mock_ai_module("ai_yellow_cartoon_sitcom"),
    ]

    for module in modules:
        assert module.config_schema
        field = module.config_schema[0]
        assert field["key"] == "custom_prompt"
        assert field["type"] == "text"
        assert field["default"] == ""


def test_ai_helper_uses_selected_model():
    settings = MagicMock(ai_image_provider="openai", ai_image_model="gpt-image-1-mini", ai_image_hourly_limit=10)
    image_bytes = _fake_image_bytes()
    captured = {}

    async def fake_openai(api_key: str, image: bytes, prompt: str, model: str):
        captured["provider"] = api_key
        captured["model"] = model
        return _fake_image_bytes()

    with (
        patch("app.services.generation.ai_image.reserve_ai_usage", lambda *args, **kwargs: None),
        patch(
            "app.services.generation.ai_image._decrypt_provider_key",
            return_value="api-key",
        ),
        patch(
            "app.services.generation.ai_image._generate_with_openai",
            fake_openai,
        ),
    ):
        result = asyncio.run(generate_ai_image(settings, image_bytes, "prompt"))

    assert result.model == "gpt-image-1-mini"
    assert captured["model"] == "gpt-image-1-mini"

    settings.ai_image_provider = "gemini"
    settings.ai_image_model = "gemini-3-pro-image-preview"
    captured.clear()

    async def fake_gemini(api_key: str, image: bytes, prompt: str, model: str):
        captured["model"] = model
        return _fake_image_bytes()

    with (
        patch("app.services.generation.ai_image.reserve_ai_usage", lambda *args, **kwargs: None),
        patch(
            "app.services.generation.ai_image._decrypt_provider_key",
            return_value="api-key",
        ),
        patch(
            "app.services.generation.ai_image._generate_with_gemini",
            fake_gemini,
        ),
    ):
        result = asyncio.run(generate_ai_image(settings, image_bytes, "prompt"))

    assert result.model == "gemini-3-pro-image-preview"
    assert captured["model"] == "gemini-3-pro-image-preview"


def test_generate_ai_image_with_prompt_enrichment():
    settings = MagicMock(
        ai_image_provider="openai",
        ai_image_model="gpt-image-1",
        ai_image_hourly_limit=10,
        default_ai_provider="openai",
        default_ai_model="gpt-4o-mini",
        ai_prompt_enrichment=True,
    )
    image_bytes = _fake_image_bytes()
    captured = {}

    async def fake_openai(api_key: str, image: bytes, prompt: str, model: str):
        captured["prompt"] = prompt
        return _fake_image_bytes()

    # Mock describe_image and fuse_prompts
    mock_describe = AsyncMock(return_value="a lovely cat sleeping")
    mock_fuse = AsyncMock(return_value="lovely cat sleeping, digital art, high quality")

    with (
        patch("app.services.generation.ai_image.reserve_ai_usage", lambda *args, **kwargs: None),
        patch(
            "app.services.generation.ai_image._decrypt_provider_key",
            return_value="api-key",
        ),
        patch(
            "app.services.generation.ai_vision.describe_image",
            mock_describe,
        ),
        patch(
            "app.services.generation.ai_vision.fuse_prompts",
            mock_fuse,
        ),
        patch(
            "app.services.generation.ai_image._generate_with_openai",
            fake_openai,
        ),
    ):
        asyncio.run(generate_ai_image(settings, image_bytes, "digital art"))

    assert captured["prompt"] == "lovely cat sleeping, digital art, high quality"
    mock_describe.assert_called_once_with(settings, image_bytes, context_hint=None)
    mock_fuse.assert_called_once_with(settings, "a lovely cat sleeping", "digital art", context_hint=None)


def test_ai_modules_forward_people_context_to_generation():
    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=_fake_image_bytes())
    client.get_asset_thumbnail = AsyncMock(return_value=(_fake_image_bytes(), "image/png"))
    client.get_asset_info = AsyncMock(
        return_value={
            "people": [
                {
                    "id": "person-1",
                    "name": "Alice",
                    "faces": [
                        {
                            "id": "face-1",
                            "imageWidth": 400,
                            "imageHeight": 300,
                            "boundingBoxX1": 0,
                            "boundingBoxY1": 0,
                            "boundingBoxX2": 100,
                            "boundingBoxY2": 120,
                        }
                    ],
                }
            ]
        }
    )
    settings = MagicMock(default_ai_provider="openai")
    asset = SimpleNamespace(
        id="asset-1", original_file_name="photo.jpg", people=[SimpleNamespace(id="person-1", name="Alice")]
    )
    ai_result = SimpleNamespace(image_bytes=_fake_image_bytes(), provider="openai", model="gpt-image-1")
    captured: dict[str, object] = {}

    async def fake_generate(settings, image_bytes, prompt, *args, **kwargs):
        captured["context_hint"] = kwargs.get("context_hint")
        captured["prompt"] = prompt
        return ai_result

    with patch("app.services.generation.modules.ai_style_base.generate_ai_image", fake_generate):
        result = asyncio.run(_create_mock_ai_module("ai_anime").run([asset], {}, client, settings))

    assert result.generation_type == "ai_anime"
    assert (
        captured["context_hint"]
        == "Immich identified these people in the source photo: person 1. Face positions: person 1 is in the upper left."
    )
    assert "people_context" in result.config
    assert result.config["people_context"]["names"] == ["Alice"]


def test_ai_modules_include_album_exif_and_people_in_prompt_enrichment_context():
    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=_fake_image_bytes())
    client.get_asset_thumbnail = AsyncMock(return_value=(_fake_image_bytes(), "image/png"))
    client.get_asset_exif = AsyncMock(return_value={"make": "Sony", "model": "A7", "iso": 400})
    client.get_asset_info = AsyncMock(
        return_value={
            "people": [
                {
                    "id": "person-1",
                    "name": "Alice",
                    "faces": [
                        {
                            "id": "face-1",
                            "imageWidth": 400,
                            "imageHeight": 300,
                            "boundingBoxX1": 0,
                            "boundingBoxY1": 0,
                            "boundingBoxX2": 100,
                            "boundingBoxY2": 120,
                        }
                    ],
                }
            ]
        }
    )
    settings = MagicMock(default_ai_provider="openai", ai_prompt_enrichment=True)
    settings._generation_album_name = "Vacation Album"
    asset = SimpleNamespace(
        id="asset-1", original_file_name="photo.jpg", people=[SimpleNamespace(id="person-1", name="Alice")]
    )
    ai_result = SimpleNamespace(image_bytes=_fake_image_bytes(), provider="openai", model="gpt-image-1")
    captured: dict[str, object] = {}

    async def fake_generate(settings, image_bytes, prompt, *args, **kwargs):
        captured["context_hint"] = kwargs.get("context_hint")
        captured["prompt_enrichment_context_hint"] = kwargs.get("prompt_enrichment_context_hint")
        return ai_result

    with patch("app.services.generation.modules.ai_style_base.generate_ai_image", fake_generate):
        result = asyncio.run(_create_mock_ai_module("ai_anime").run([asset], {}, client, settings))

    assert result.generation_type == "ai_anime"
    assert (
        captured["context_hint"]
        == "Immich identified these people in the source photo: person 1. Face positions: person 1 is in the upper left."
    )
    assert captured["prompt_enrichment_context_hint"] == (
        "Album: Vacation Album\n"
        "Detected people: person 1\n"
        "Immich identified these people in the source photo: person 1. Face positions: person 1 is in the upper left.\n"
        "EXIF: Camera: Sony A7; Exposure: ISO 400"
    )
    assert result.config["prompt_enrichment_context"]["album_name"] == "Vacation Album"
    # Ensure original names are stored in config
    assert result.config["prompt_enrichment_context"]["people_names"] == ["Alice"]
    client.get_asset_exif.assert_awaited_once_with("asset-1")
