from __future__ import annotations

import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

from PIL import Image

from app.services.generation.modules.motion_cinemagraph import MotionCinemagraphModule


def _asset():
    asset = MagicMock()
    asset.id = "asset-1"
    asset.original_file_name = "photo.jpg"
    return asset


def _image_bytes():
    image = Image.new("RGB", (200, 200), color=(100, 150, 200))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_motion_cinemagraph_metadata():
    module = MotionCinemagraphModule()
    assert module.name == "motion_cinemagraph"
    assert module.label == "Motion Cinemagraph"
    assert module.source_asset_count == 1
    assert module.default_config["motion_type"] == "glow"


def test_motion_cinemagraph_generates_gif():
    module = MotionCinemagraphModule()
    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=_image_bytes())

    async def run_test():
        return await module.run(
            page_items=[_asset()],
            config={"mask_region": "center", "motion_type": "glow", "speed": 1.0},
            client=client,
            settings=None,
        )

    result = asyncio.run(run_test())

    assert result.generation_type == "motion_cinemagraph"
    assert result.output_format == "gif"
    assert result.frame_count == 24
    assert result.image_bytes.startswith(b"GIF")
