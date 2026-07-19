from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png


def _shift_with_edge_fill(arr: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Shift an HxWxC array by (dx, dy), replicating edge pixels.

    Avoids the wrap-around artifact of ``ImageChops.offset``.
    """
    h, w = arr.shape[:2]
    if dx == 0 and dy == 0:
        return arr
    sx0 = max(0, dx)
    sy0 = max(0, dy)
    sx1 = min(w, w + dx)
    sy1 = min(h, h + dy)
    region = arr[sy0:sy1, sx0:sx1]
    out = np.empty_like(arr)
    dx0 = max(0, -dx)
    dy0 = max(0, -dy)
    dx1 = dx0 + (sx1 - sx0)
    dy1 = dy0 + (sy1 - sy0)
    out[dy0:dy1, dx0:dx1] = region
    if dy0 > 0:
        out[:dy0, :] = out[dy0 : dy0 + 1, :]
    if dy1 < h:
        out[dy1:, :] = out[dy1 - 1 : dy1, :]
    if dx0 > 0:
        out[:, :dx0] = out[:, dx0 : dx0 + 1]
    if dx1 < w:
        out[:, dx1:] = out[:, dx1 - 1 : dx1]
    return out


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

        # Scale shifts relative to image size so they read consistently across
        # different resolutions (default values were tuned for ~1000px images).
        base = max(source.size)
        size_factor = max(0.6, min(1.6, base / 1000.0))
        eff_shift = max(4, int(shift * size_factor))

        arr = np.asarray(source, dtype=np.uint8).copy()
        # More dramatic RGB channel shifts, edge-replicated (no wrap-around)
        r_dx = random.randint(eff_shift // 2, eff_shift)
        r_dy = random.randint(-eff_shift // 4, eff_shift // 4)
        g_dx = random.randint(-eff_shift // 3, eff_shift // 3)
        b_dx = random.randint(-eff_shift, -eff_shift // 2)
        b_dy = random.randint(-eff_shift // 4, eff_shift // 4)
        arr[..., 0] = _shift_with_edge_fill(arr[..., 0], r_dx, r_dy)
        arr[..., 1] = _shift_with_edge_fill(arr[..., 1], g_dx, 0)
        arr[..., 2] = _shift_with_edge_fill(arr[..., 2], b_dx, b_dy)
        merged = Image.fromarray(arr, "RGB")

        if style == "bold":
            # High contrast, vibrant colors
            merged = ImageEnhance.Color(merged).enhance(1.3)
            merged = ImageEnhance.Contrast(merged).enhance(1.35)
            merged = ImageEnhance.Sharpness(merged).enhance(1.5)

            # Soft glow from bright edges (Sobel-like) instead of a hard 1px outline.
            # FIND_EDGES gives a single-pixel contour; blurring it creates a
            # prismatic halo that emphasizes the chromatic split.
            edges = merged.filter(ImageFilter.FIND_EDGES)
            edges = edges.filter(ImageFilter.GaussianBlur(radius=2))
            edges = ImageOps.grayscale(edges)
            edges = ImageEnhance.Brightness(edges).enhance(0.5)
            edges = ImageOps.colorize(edges, black=(0, 0, 0), white=(255, 255, 255))
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
            model="pil+numpy",
            config={"shift": shift, "style": style},
            source_asset_ids=[asset.id],
        )
