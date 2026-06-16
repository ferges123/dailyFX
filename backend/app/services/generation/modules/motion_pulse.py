from __future__ import annotations

import math
import random

from PIL import ImageChops, ImageEnhance

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import frames_to_animation, load_rgb


class MotionPulseModule:
    name = "motion_pulse"
    label = "Motion Pulse"
    description = "Animated pulsing brightness, saturation, hue, or glitch effect."
    default_weight = 1
    source_asset_count = 1
    default_config = {"effect": "brightness", "speed": 1.0, "intensity": 0.6}
    config_schema = [
        {
            "key": "effect",
            "label": "Effect",
            "type": "select",
            "description": "Animated parameter to modulate.",
            "default": "brightness",
            "options": [
                {"value": "brightness", "label": "Brightness"},
                {"value": "saturation", "label": "Saturation"},
                {"value": "hue", "label": "Hue"},
                {"value": "glitch", "label": "Glitch"},
            ],
        },
        {
            "key": "speed",
            "label": "Speed",
            "type": "number",
            "description": "Animation speed multiplier.",
            "default": 1.0,
            "min": 0.5,
            "max": 2.0,
            "step": 0.1,
        },
        {
            "key": "intensity",
            "label": "Intensity",
            "type": "number",
            "description": "Effect intensity.",
            "default": 0.6,
            "min": 0.3,
            "max": 1.0,
            "step": 0.1,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        source = load_rgb(await client.get_asset_data(asset.id))
        effect = str(config.get("effect") or "brightness")
        speed = max(0.5, min(2.0, float(config.get("speed", 1.0) or 1.0)))
        intensity = max(0.3, min(1.0, float(config.get("intensity", 0.6) or 0.6)))
        frame_count = 24
        frames = []
        random_seed = int(config.get("seed", 0) or 0)
        rng = random.Random(random_seed)

        for index in range(frame_count):
            phase = math.sin((index / frame_count) * 2 * math.pi)
            if effect == "brightness":
                frame = ImageEnhance.Brightness(source).enhance(1.0 + phase * intensity * 0.35)
            elif effect == "saturation":
                frame = ImageEnhance.Color(source).enhance(1.0 + phase * intensity * 0.45)
            elif effect == "hue":
                r, g, b = source.split()
                shift = int(phase * intensity * 24)
                frame = ImageChops.offset(r, shift, 0)
                frame = ImageChops.merge("RGB", (frame, g, ImageChops.offset(b, -shift, 0)))
            elif effect == "glitch":
                r, g, b = source.split()
                shift = rng.randint(-6, 6) if index % 3 == 0 else 0
                frame = ImageChops.merge("RGB", (ImageChops.offset(r, shift, 0), g, ImageChops.offset(b, -shift, 0)))
            else:
                frame = source.copy()
            frames.append(frame)

        output = frames_to_animation(frames, fps=int(12 * speed), output_format="gif")
        return GenerationResult(
            title=f"Motion Pulse: {asset.original_file_name or asset.id}",
            summary=f"Animated {effect} pulse effect.",
            image_bytes=output,
            generation_type=self.name,
            provider="local",
            model="pil+imageio",
            config={"effect": effect, "speed": speed, "intensity": intensity},
            source_asset_ids=[asset.id],
            output_format="gif",
            frame_count=frame_count,
        )
