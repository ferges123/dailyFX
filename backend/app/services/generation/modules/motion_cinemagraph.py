from __future__ import annotations

import math

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import frames_to_animation, load_rgb


class MotionCinemagraphModule:
    name = "motion_cinemagraph"
    label = "Motion Cinemagraph"
    description = "Create cinemagraphs with localized motion masks."
    default_weight = 1
    source_asset_count = 1
    default_config = {"mask_region": "center", "motion_type": "glow", "speed": 1.0}
    config_schema = [
        {
            "key": "mask_region",
            "label": "Mask Region",
            "type": "select",
            "description": "Area to isolate and animate.",
            "default": "center",
            "options": [
                {"value": "center", "label": "Center"},
                {"value": "face", "label": "Face (Fallback Center)"},
            ],
        },
        {
            "key": "motion_type",
            "label": "Motion Type",
            "type": "select",
            "description": "Animation pattern to apply to mask.",
            "default": "glow",
            "options": [
                {"value": "glow", "label": "Pulsing Glow"},
                {"value": "water", "label": "Water Ripple"},
                {"value": "clouds", "label": "Cloud Drift"},
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
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        source = load_rgb(await client.get_asset_data(asset.id))
        mask_region = str(config.get("mask_region") or "center")
        motion_type = str(config.get("motion_type") or "glow")
        speed = max(0.5, min(2.0, float(config.get("speed", 1.0) or 1.0)))

        width, height = source.size
        frame_count = 24
        fps = int(12 * speed)

        # Create mask
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        cx, cy = width / 2, height / 2
        rx, ry = width * 0.35, height * 0.35
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
        # Blur the mask to make the transition smooth
        blur_radius = max(5, int(min(width, height) * 0.08))
        mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        frames = []
        for index in range(frame_count):
            t = index / frame_count
            phase = math.sin(t * 2 * math.pi)

            if motion_type == "glow":
                # Glow effect: modulate brightness and color saturation
                glow_img = ImageEnhance.Brightness(source).enhance(1.0 + phase * 0.25)
                glow_img = ImageEnhance.Color(glow_img).enhance(1.0 + phase * 0.15)
                frame = Image.composite(glow_img, source, mask)
            elif motion_type == "water":
                # Water ripple: circular offset path
                dx = int(8 * math.sin(t * 2 * math.pi))
                dy = int(8 * math.cos(t * 2 * math.pi))
                shifted = ImageChops.offset(source, dx, dy)
                frame = Image.composite(shifted, source, mask)
            elif motion_type == "clouds":
                # Cloud drift: horizontal drift
                dx = int(15 * t)
                shifted = ImageChops.offset(source, dx, 0)
                frame = Image.composite(shifted, source, mask)
            else:
                frame = source.copy()

            frames.append(frame)

        output = frames_to_animation(frames, fps=fps, output_format="gif")
        return GenerationResult(
            title=f"Motion Cinemagraph: {asset.original_file_name or asset.id}",
            summary=f"Animated {motion_type} cinemagraph.",
            image_bytes=output,
            generation_type=self.name,
            provider="local",
            model="pil+imageio",
            config={"mask_region": mask_region, "motion_type": motion_type, "speed": speed},
            source_asset_ids=[asset.id],
            output_format="gif",
            frame_count=frame_count,
        )
