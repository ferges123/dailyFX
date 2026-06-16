from __future__ import annotations

import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

from PIL import Image

from app.services.generation.modules.motion_pulse import MotionPulseModule


def _asset():
    asset = MagicMock()
    asset.id = "asset-1"
    asset.original_file_name = "photo.jpg"
    return asset


def _image_bytes():
    image = Image.new("RGB", (120, 120), color=(120, 120, 120))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_motion_pulse_metadata():
    module = MotionPulseModule()
    assert module.name == "motion_pulse"
    assert module.label == "Motion Pulse"
    assert module.source_asset_count == 1
    assert module.default_config["effect"] == "brightness"


def test_motion_pulse_generates_gif():
    module = MotionPulseModule()
    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=_image_bytes())

    async def run_test():
        return await module.run(
            page_items=[_asset()],
            config={"effect": "brightness", "speed": 1.0, "intensity": 0.5},
            client=client,
            settings=None,
        )

    result = asyncio.run(run_test())

    assert result.generation_type == "motion_pulse"
    assert result.output_format == "gif"
    assert result.frame_count == 24
    assert result.image_bytes.startswith(b"GIF")
