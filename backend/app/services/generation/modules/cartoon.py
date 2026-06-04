from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

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

        # Quantize colors
        color = (color // (256 // color_levels) * (256 // color_levels)).astype(np.uint8)

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

        # Combine: multiply color by edge mask
        result_cv = cv2.bitwise_and(color, edges_bgr)
        result = Image.fromarray(cv2.cvtColor(result_cv, cv2.COLOR_BGR2RGB))

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
