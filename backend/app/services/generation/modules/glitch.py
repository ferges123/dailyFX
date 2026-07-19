from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageEnhance

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png


def _shift_with_edge_fill(arr: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Shift an HxWxC array by (dx, dy), replicating edge pixels.

    Avoids the wrap-around artifact of ``np.roll`` / ``ImageChops.offset``.
    """
    h, w = arr.shape[:2]
    if dx == 0 and dy == 0:
        return arr
    # Source window in the original image
    sx0 = max(0, dx)
    sy0 = max(0, dy)
    sx1 = min(w, w + dx)
    sy1 = min(h, h + dy)
    region = arr[sy0:sy1, sx0:sx1]
    out = np.empty_like(arr)
    # Destination window in the output image
    dx0 = max(0, -dx)
    dy0 = max(0, -dy)
    dx1 = dx0 + (sx1 - sx0)
    dy1 = dy0 + (sy1 - sy0)
    out[dy0:dy1, dx0:dx1] = region
    # Replicate edges to fill exposed borders
    if dy0 > 0:
        out[:dy0, :] = out[dy0 : dy0 + 1, :]
    if dy1 < h:
        out[dy1:, :] = out[dy1 - 1 : dy1, :]
    if dx0 > 0:
        out[:, :dx0] = out[:, dx0 : dx0 + 1]
    if dx1 < w:
        out[:, dx1:] = out[:, dx1 - 1 : dx1]
    return out


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

        arr = np.asarray(source, dtype=np.uint8).copy()
        height, width = arr.shape[:2]

        # RGB channel shifts with edge replication (no wrap-around artifacts)
        r_dx = int(random.randint(-shift, shift) * intensity)
        g_dx = int(random.randint(-shift, shift) * 0.5 * intensity)
        b_dx = int(random.randint(-shift, shift) * intensity)
        r_dy = int(random.randint(-shift // 2, shift // 2) * intensity * 0.4)
        b_dy = int(random.randint(-shift // 2, shift // 2) * intensity * 0.4)
        arr[..., 0] = _shift_with_edge_fill(arr[..., 0], r_dx, r_dy)
        arr[..., 1] = _shift_with_edge_fill(arr[..., 1], g_dx, 0)
        arr[..., 2] = _shift_with_edge_fill(arr[..., 2], b_dx, b_dy)

        merged = Image.fromarray(arr, "RGB")

        # Subtle enhancement
        merged = ImageEnhance.Contrast(merged).enhance(1.15)
        merged = ImageEnhance.Sharpness(merged).enhance(1.2)
        merged = ImageEnhance.Color(merged).enhance(1.1)

        # Scanlines via numpy: classic CRT pattern with soft falloff.
        # Darkens every 2nd row by ~intensity-dependent amount; every 4th row
        # gets a slightly stronger line for the double-stripe CRT look.
        arr = np.asarray(merged, dtype=np.float32)
        row_factor = np.ones(height, dtype=np.float32)
        # Even rows get a subtle darkening
        darkening = 0.10 * intensity
        row_factor[0::2] = 1.0 - darkening
        # Every 4th row gets slightly more (double-stripe pattern)
        row_factor[0::4] = 1.0 - darkening * 1.6
        arr = arr * row_factor[:, None, None]
        arr = arr.clip(0.0, 255.0).astype(np.uint8)

        # Selective row distortion via numpy slicing (with edge-fill, no wrap)
        row_height = 32
        n_rows = height // row_height
        if n_rows > 0:
            shift_mask = np.random.random(n_rows) < 0.3 * intensity
            offsets = np.zeros(n_rows, dtype=np.int32)
            offsets[shift_mask] = np.random.randint(-shift // 2, shift // 2 + 1, size=shift_mask.sum())
            for i in range(n_rows):
                if offsets[i] != 0:
                    y_start = i * row_height
                    y_end = min(y_start + row_height, height)
                    arr[y_start:y_end] = _shift_with_edge_fill(arr[y_start:y_end], offsets[i], 0)

        glitched = Image.fromarray(arr, "RGB")

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
