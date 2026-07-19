from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, load_rgb, save_png


class PencilSketchModule:
    name = "pencil_sketch"
    label = "Pencil Sketch"
    description = "Hand-drawn pencil sketch using OpenCV."
    default_weight = 2
    default_config = {"style": "gray", "shade_factor": 0.05}
    config_schema = [
        {
            "key": "style",
            "label": "Style",
            "type": "select",
            "options": [
                {"value": "gray", "label": "Grayscale"},
                {"value": "color", "label": "Color"},
            ],
            "default": "gray",
        },
        {
            "key": "shade_factor",
            "label": "Shade intensity",
            "type": "number",
            "description": "Shading strength (0.02 = light, 0.1 = dark).",
            "min": 0.02,
            "max": 0.1,
            "step": 0.01,
            "default": 0.05,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)

        style = config.get("style", "gray")
        shade = max(0.02, min(0.1, float(config.get("shade_factor", 0.05) or 0.05)))

        img_cv = cv2.cvtColor(np.array(source), cv2.COLOR_RGB2BGR)
        gray_sketch, color_sketch = cv2.pencilSketch(img_cv, sigma_s=60, sigma_r=0.07, shade_factor=shade)

        if style == "color":
            result = Image.fromarray(cv2.cvtColor(color_sketch, cv2.COLOR_BGR2RGB))
        else:
            # Boost contrast of the grayscale sketch — pencilSketch tends to
            # produce a flat, washed-out look. A contrast + sharpness lift
            # brings back the graphite texture.
            result = Image.fromarray(gray_sketch).convert("RGB")
            result = ImageEnhance.Contrast(result).enhance(1.25)
            result = ImageEnhance.Sharpness(result).enhance(1.2)

        # Composite the sketch onto a paper-tone background instead of pure
        # white — real pencil sketches are on cream/off-white paper. A pure
        # white background reads as digital, not hand-drawn.
        paper_color = (248, 244, 235)  # warm off-white
        w, h = result.size
        paper_bg = Image.new("RGB", (w, h), paper_color)
        # Multiply blend: dark strokes stay dark, white paper -> paper color
        result = ImageChops.multiply(paper_bg, result)

        # Subtle paper grain — gives the graphite something to "sit on"
        result = add_grain(result, strength=0.04, blur=0.2)

        return GenerationResult(
            title=f"Pencil Sketch: {asset.original_file_name or asset.id}",
            summary=f"Hand-drawn {style} pencil sketch.",
            image_bytes=save_png(result),
            generation_type="pencil_sketch",
            provider="local",
            model="opencv+pil",
            config={"style": style, "shade_factor": shade},
            source_asset_ids=[asset.id],
        )
