from __future__ import annotations

import random

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png


class PrismSplitModule:
    name = "prism_split"
    label = "Prism Split"
    description = "Bold chromatic aberration with prismatic color split."
    default_weight = 2
    default_config = {"shift": 18, "style": "bold"}
    config_schema = [
        {
            "key": "shift",
            "label": "Shift",
            "type": "number",
            "description": "Maximum chromatic offset in pixels.",
            "min": 6,
            "max": 40,
            "step": 2,
            "default": 18,
        },
        {
            "key": "style",
            "label": "Style",
            "type": "select",
            "description": "Effect style.",
            "options": [
                {"value": "bold", "label": "Bold (high contrast)"},
                {"value": "subtle", "label": "Subtle (soft blend)"},
            ],
            "default": "bold",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)
        shift = max(6, int(config.get("shift", 18) or 18))
        style = config.get("style", "bold")

        # Enhanced preprocessing
        source = ImageEnhance.Contrast(source).enhance(1.2)
        source = ImageEnhance.Color(source).enhance(1.15)

        # More dramatic RGB channel shifts
        r, g, b = source.split()
        r = ImageChops.offset(r, random.randint(shift // 2, shift), random.randint(-shift // 4, shift // 4))
        g = ImageChops.offset(g, random.randint(-shift // 3, shift // 3), 0)
        b = ImageChops.offset(b, random.randint(-shift, -shift // 2), random.randint(-shift // 4, shift // 4))

        merged = Image.merge("RGB", (r, g, b))

        if style == "bold":
            # High contrast, vibrant colors
            merged = ImageEnhance.Color(merged).enhance(1.3)
            merged = ImageEnhance.Contrast(merged).enhance(1.35)
            merged = ImageEnhance.Sharpness(merged).enhance(1.5)

            # Add edge glow
            edges = merged.filter(ImageFilter.FIND_EDGES)
            edges = ImageEnhance.Brightness(edges).enhance(0.3)
            merged = ImageChops.screen(merged, edges)
        else:
            # Softer, dreamy look
            merged = ImageEnhance.Color(merged).enhance(1.2)
            merged = ImageEnhance.Contrast(merged).enhance(1.2)
            merged = merged.filter(ImageFilter.GaussianBlur(radius=0.5))

        # Subtle grain and vignette
        merged = add_grain(merged, strength=0.06, blur=0.1)
        merged = apply_vignette(merged, strength=0.3)

        return GenerationResult(
            title=f"Prism Split: {asset.original_file_name or asset.id}",
            summary="Bold chromatic aberration with prismatic color split.",
            image_bytes=save_png(merged),
            generation_type="prism_split",
            provider="local",
            model="pil",
            config={"shift": shift, "style": style},
            source_asset_ids=[asset.id],
        )
