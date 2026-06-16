from __future__ import annotations

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import frames_to_animation, load_rgb


class MotionZoomPanModule:
    name = "motion_zoom_pan"
    label = "Motion Zoom/Pan"
    description = "Animated Ken Burns zoom, pan, and slide transitions."
    default_weight = 1
    source_asset_count = 1
    default_config = {"style": "ken-burns", "duration": 2.0, "intensity": 0.2}
    config_schema = [
        {
            "key": "style",
            "label": "Style",
            "type": "select",
            "description": "Zoom and pan movement style.",
            "default": "ken-burns",
            "options": [
                {"value": "zoom-in", "label": "Zoom In"},
                {"value": "zoom-out", "label": "Zoom Out"},
                {"value": "ken-burns", "label": "Ken Burns"},
                {"value": "pan-left", "label": "Pan Left"},
                {"value": "pan-right", "label": "Pan Right"},
            ],
        },
        {
            "key": "duration",
            "label": "Duration (s)",
            "type": "number",
            "description": "Animation duration in seconds.",
            "default": 2.0,
            "min": 1.0,
            "max": 4.0,
            "step": 0.5,
        },
        {
            "key": "intensity",
            "label": "Intensity",
            "type": "number",
            "description": "Movement intensity / zoom amount.",
            "default": 0.2,
            "min": 0.1,
            "max": 0.5,
            "step": 0.05,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        source = load_rgb(await client.get_asset_data(asset.id))
        style = str(config.get("style") or "ken-burns")
        duration = max(1.0, min(4.0, float(config.get("duration", 2.0) or 2.0)))
        intensity = max(0.1, min(0.5, float(config.get("intensity", 0.2) or 0.2)))

        fps = 12
        frame_count = int(duration * fps)
        width, height = source.size

        frames = []
        for index in range(frame_count):
            t = index / (frame_count - 1) if frame_count > 1 else 0.0

            if style == "zoom-in":
                scale = t * intensity
                x_offset_ratio = 0.5
                y_offset_ratio = 0.5
            elif style == "zoom-out":
                scale = (1.0 - t) * intensity
                x_offset_ratio = 0.5
                y_offset_ratio = 0.5
            elif style == "ken-burns":
                scale = t * intensity
                x_offset_ratio = t
                y_offset_ratio = t
            elif style == "pan-left":
                scale = intensity
                x_offset_ratio = 1.0 - t
                y_offset_ratio = 0.5
            elif style == "pan-right":
                scale = intensity
                x_offset_ratio = t
                y_offset_ratio = 0.5
            else:
                scale = 0.0
                x_offset_ratio = 0.5
                y_offset_ratio = 0.5

            w_crop = int(width * (1.0 - scale))
            h_crop = int(height * (1.0 - scale))
            dw = width - w_crop
            dh = height - h_crop

            x0 = int(dw * x_offset_ratio)
            y0 = int(dh * y_offset_ratio)
            x1 = x0 + w_crop
            y1 = y0 + h_crop

            cropped = source.crop((x0, y0, x1, y1))
            resized = cropped.resize((width, height))
            frames.append(resized)

        output = frames_to_animation(frames, fps=fps, output_format="gif")
        return GenerationResult(
            title=f"Motion Zoom/Pan: {asset.original_file_name or asset.id}",
            summary=f"Animated {style} zoom/pan transition.",
            image_bytes=output,
            generation_type=self.name,
            provider="local",
            model="pil+imageio",
            config={"style": style, "duration": duration, "intensity": intensity},
            source_asset_ids=[asset.id],
            output_format="gif",
            frame_count=frame_count,
        )
