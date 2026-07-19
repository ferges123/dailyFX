from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageEnhance

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import load_rgb, save_png


class CartoonModule:
    name = "cartoon"
    label = "Cartoon"
    description = "Cartoon effect with bold edges and flat colors."
    default_weight = 2
    default_config = {"edge_strength": 9, "color_levels": 8}
    config_schema = [
        {
            "key": "edge_strength",
            "label": "Edge strength",
            "type": "number",
            "description": "Edge line thickness (5 = thin, 15 = bold).",
            "min": 5,
            "max": 15,
            "step": 2,
            "default": 9,
        },
        {
            "key": "color_levels",
            "label": "Color levels",
            "type": "number",
            "description": "Color quantization (4 = flat, 16 = detailed).",
            "min": 4,
            "max": 16,
            "step": 2,
            "default": 8,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)

        edge_strength = max(5, min(15, int(config.get("edge_strength", 9) or 9)))
        # ensure odd kernel
        if edge_strength % 2 == 0:
            edge_strength += 1
        color_levels = max(4, min(16, int(config.get("color_levels", 8) or 8)))

        img_cv = cv2.cvtColor(np.array(source), cv2.COLOR_RGB2BGR)

        # Smooth colors with bilateral filter (repeated for stronger effect)
        color = img_cv
        for _ in range(3):
            color = cv2.bilateralFilter(color, d=9, sigmaColor=75, sigmaSpace=75)

        # Quantize colors using a smoothstep LUT instead of hard integer
        # division. Integer division (color // step * step) produces visible
        # banding because each level has a hard edge; a smoothstep between
        # levels softens the transitions while still looking "flat".
        color = _smooth_posterize(color, color_levels)

        # Edge detection on grayscale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        edges = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            blockSize=edge_strength,
            C=9,
        )
        edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

        # Combine: multiply color by edge mask. Where edges are black (0),
        # the result is black; where edges are white (255), the color shows
        # through unchanged.
        result_cv = cv2.bitwise_and(color, edges_bgr)

        # Tint the pure-black background slightly toward a warm off-white
        # for an illustrated feel — pure black reads as digital, while a
        # tinted dark gives a hand-drawn ink look.
        bg_tint = np.full_like(result_cv, (35, 30, 28), dtype=np.uint8)
        # Where edges are black (no color), blend in the bg tint at low alpha
        no_color_mask = cv2.cvtColor(cv2.bitwise_not(edges_bgr), cv2.COLOR_BGR2GRAY)
        no_color_alpha = (no_color_mask > 0).astype(np.float32) * 0.5
        result_cv = (
            result_cv.astype(np.float32) * (1 - no_color_alpha[:, :, None])
            + bg_tint.astype(np.float32) * no_color_alpha[:, :, None]
        ).astype(np.uint8)

        # Slight saturation boost for a more vibrant cartoon look
        result = Image.fromarray(cv2.cvtColor(result_cv, cv2.COLOR_BGR2RGB))
        result = ImageEnhance.Color(result).enhance(1.1)

        return GenerationResult(
            title=f"Cartoon: {asset.original_file_name or asset.id}",
            summary="Cartoon effect with bold edges and flat colors.",
            image_bytes=save_png(result),
            generation_type="cartoon",
            provider="local",
            model="opencv",
            config={"edge_strength": edge_strength, "color_levels": color_levels},
            source_asset_ids=[asset.id],
        )


def _smooth_posterize(img: np.ndarray, levels: int) -> np.ndarray:
    """Posterize with smoothstep transitions between levels.

    Standard integer division (img // step * step) produces hard banding
    at each level boundary. This LUT-based approach applies a smoothstep
    between adjacent levels, which softens the banding while preserving the
    flat-color cartoon look.
    """
    step = 256 // levels
    # Build per-level smoothstep LUT
    lut = np.zeros(256, dtype=np.uint8)
    for i in range(levels):
        center = i * step + step // 2
        # Output value at center of band i
        out_center = i * step
        # Smoothstep within ±step/2 of center
        for v in range(256):
            offset = v - center
            if abs(offset) > step:
                continue
            t = offset / step + 0.5  # 0..1 within the band
            t = np.clip(t, 0.0, 1.0)
            t = t * t * (3.0 - 2.0 * t)  # smoothstep
            target_next = min(255, (i + 1) * step)
            lut[v] = int(out_center + (target_next - out_center) * t)
    # Apply LUT to each channel
    return cv2.LUT(img, lut)
