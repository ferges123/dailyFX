from __future__ import annotations

import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

from PIL import Image

from app.services.generation.modules.motion_zoom_pan import MotionZoomPanModule


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


def test_motion_zoom_pan_metadata():
    module = MotionZoomPanModule()
    assert module.name == "motion_zoom_pan"
    assert module.label == "Motion Zoom/Pan"
    assert module.source_asset_count == 1
    assert module.default_config["style"] == "ken-burns"


def test_motion_zoom_pan_generates_gif():
    module = MotionZoomPanModule()
    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=_image_bytes())

    async def run_test():
        return await module.run(
            page_items=[_asset()],
            config={"style": "ken-burns", "duration": 2.0, "intensity": 0.2},
            client=client,
            settings=None,
        )

    result = asyncio.run(run_test())

    assert result.generation_type == "motion_zoom_pan"
    assert result.output_format == "gif"
    assert result.frame_count == 24
    assert result.image_bytes.startswith(b"GIF")
