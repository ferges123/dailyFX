from __future__ import annotations

import random

from PIL import Image, ImageChops, ImageEnhance

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png


class GlitchModule:
    name = "glitch"
    label = "Glitch"
    description = "RGB channel shifts, scanlines, and horizontal distortion."
    default_weight = 2
    default_config = {"shift": 8, "intensity": 0.6}
    config_schema = [
        {
            "key": "shift",
            "label": "Shift",
            "type": "number",
            "description": "Maximum horizontal channel displacement in pixels.",
            "min": 3,
            "max": 24,
            "step": 1,
            "default": 8,
        },
        {
            "key": "intensity",
            "label": "Intensity",
            "type": "number",
            "description": "Effect intensity (0.3 = subtle, 1.0 = extreme).",
            "min": 0.3,
            "max": 1.0,
            "step": 0.1,
            "default": 0.6,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)
        shift = max(2, int(config.get("shift", 8) or 8))
        intensity = max(0.3, min(1.0, float(config.get("intensity", 0.6) or 0.6)))

        # Softer RGB channel shifts
        r, g, b = source.split()
        r = ImageChops.offset(r, int(random.randint(-shift, shift) * intensity), 0)
        g = ImageChops.offset(g, int(random.randint(-shift, shift) * 0.5 * intensity), 0)
        b = ImageChops.offset(b, int(random.randint(-shift, shift) * intensity), 0)
        merged = Image.merge("RGB", (r, g, b))

        # Subtle enhancement
        merged = ImageEnhance.Contrast(merged).enhance(1.15)
        merged = ImageEnhance.Sharpness(merged).enhance(1.2)
        merged = ImageEnhance.Color(merged).enhance(1.1)

        # Softer scanlines
        width, height = merged.size
        scanlines = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for y in range(0, height, 3):
            if y % 6 == 0:
                scanlines.paste((8, 8, 12, int(25 * intensity)), (0, y, width, min(height, y + 1)))
        merged = Image.alpha_composite(merged.convert("RGBA"), scanlines).convert("RGB")

        # Selective row distortion (fewer rows)
        rows = []
        row_height = 32
        for y in range(0, height, row_height):
            slice_img = merged.crop((0, y, width, min(height, y + row_height)))
            if random.random() < 0.3 * intensity:  # Only 30% of rows
                slice_img = ImageChops.offset(slice_img, random.randint(-shift // 2, shift // 2), 0)
            rows.append(slice_img)

        glitched = Image.new("RGB", (width, height))
        cursor = 0
        for row in rows:
            glitched.paste(row, (0, cursor))
            cursor += row.size[1]

        # Subtle grain and vignette
        glitched = add_grain(glitched, strength=0.05, blur=0.15)
        glitched = apply_vignette(glitched, strength=0.25)

        return GenerationResult(
            title=f"Glitch: {asset.original_file_name or asset.id}",
            summary="Refined chromatic glitch with subtle distortion.",
            image_bytes=save_png(glitched),
            generation_type="glitch",
            provider="local",
            model="pil",
            config={"shift": shift, "intensity": intensity},
            source_asset_ids=[asset.id],
        )
