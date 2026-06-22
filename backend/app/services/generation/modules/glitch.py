from __future__ import annotations

import random

import numpy as np
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

        # Scanlines via numpy — much faster than per-row paste loop
        width, height = merged.size
        arr = np.array(merged, dtype=np.uint8)

        # Build scanline mask: dark line every 3rd row, skip every 6th (pattern: 2 dark, 1 gap)
        scanline_alpha = np.zeros(height, dtype=np.float32)
        scanline_alpha[0::3] = 25.0 * intensity  # every 3rd row
        scanline_alpha[0::6] = 0.0               # but not every 6th (creates double-line pattern)

        # Apply scanlines: darken affected rows
        scanline_mask = (1.0 - scanline_alpha[:, np.newaxis] / 255.0)
        arr = (arr.astype(np.float32) * scanline_mask[:, np.newaxis]).astype(np.uint8)

        # Selective row distortion via numpy slicing
        row_height = 32
        n_rows = height // row_height
        if n_rows > 0:
            # Decide which rows get shifted (30% chance each)
            shift_mask = np.random.random(n_rows) < 0.3 * intensity
            # Generate random offsets for selected rows
            offsets = np.zeros(n_rows, dtype=np.int32)
            offsets[shift_mask] = np.random.randint(-shift // 2, shift // 2 + 1, size=shift_mask.sum())

            for i in range(n_rows):
                if offsets[i] != 0:
                    y_start = i * row_height
                    y_end = min(y_start + row_height, height)
                    arr[y_start:y_end] = np.roll(arr[y_start:y_end], offsets[i], axis=1)

        glitched = Image.fromarray(arr)

        # Subtle grain and vignette
        glitched = add_grain(glitched, strength=0.05, blur=0.15)
        glitched = apply_vignette(glitched, strength=0.25)

        return GenerationResult(
            title=f"Glitch: {asset.original_file_name or asset.id}",
            summary="Refined chromatic glitch with subtle distortion.",
            image_bytes=save_png(glitched),
            generation_type="glitch",
            provider="local",
            model="pil+numpy",
            config={"shift": shift, "intensity": intensity},
            source_asset_ids=[asset.id],
        )
