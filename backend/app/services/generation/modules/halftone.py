from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png, select_palette


class HalftoneModule:
    name = "halftone"
    label = "Halftone"
    description = "Artistic halftone with varied dot sizes and depth."
    default_weight = 2
    default_config = {"cell_size": 14, "style": "varied"}
    config_schema = [
        {
            "key": "cell_size",
            "label": "Cell size",
            "type": "number",
            "description": "Larger values create coarser dots.",
            "min": 8,
            "max": 32,
            "step": 1,
            "default": 14,
        },
        {
            "key": "style",
            "label": "Style",
            "type": "select",
            "description": "Dot pattern style.",
            "options": [
                {"value": "varied", "label": "Varied (organic)"},
                {"value": "uniform", "label": "Uniform (classic)"},
            ],
            "default": "varied",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)
        cell_size = max(8, int(config.get("cell_size", 14) or 14))
        style = config.get("style", "varied")
        dark, light = select_palette(config)

        # Enhanced preprocessing
        gray = ImageOps.grayscale(source)
        gray = ImageEnhance.Contrast(gray).enhance(1.3)
        gray = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=120))

        width, height = gray.size
        canvas = Image.new("RGB", (width, height), light)
        draw = ImageDraw.Draw(canvas)

        # Vectorized dot generation via numpy downsampling
        gray_arr = np.array(gray, dtype=np.float64)

        # Downsample to grid: average each cell
        rows = height // cell_size
        cols = width // cell_size
        if rows == 0 or cols == 0:
            # Image smaller than cell_size, skip dots
            overlay = ImageOps.colorize(gray, black=dark, white=light)
            mixed = Image.blend(canvas, overlay, 0.25)
        else:
            cropped = gray_arr[: rows * cell_size, : cols * cell_size]
            grid = cropped.reshape(rows, cell_size, cols, cell_size).mean(axis=(1, 3))
            # ratio: 0=light (small dot), 1=dark (big dot)
            ratios = np.clip(1.0 - grid / 255.0, 0.1, 1.0)

            max_radius = cell_size / 2.2

            if style == "varied":
                jitters = np.random.uniform(0.85, 1.15, size=ratios.shape)
                radii = (max_radius * ratios * jitters).astype(np.int32)
                radii = np.maximum(radii, 1)
                offsets_x = np.random.randint(-2, 3, size=ratios.shape)
                offsets_y = np.random.randint(-2, 3, size=ratios.shape)
            else:
                radii = (max_radius * ratios).astype(np.int32)
                radii = np.maximum(radii, 1)
                offsets_x = np.zeros_like(radii)
                offsets_y = np.zeros_like(radii)

            cy_base = np.arange(rows) * cell_size + cell_size // 2
            cx_base = np.arange(cols) * cell_size + cell_size // 2

            # Two-layer dots: a darker mid-color ring gives the dots a softer
            # transition into the background (dot gain) instead of hard disks.
            mid_color = tuple(int(dark[i] * 0.7 + light[i] * 0.3) for i in range(3))

            # Collect ellipse boxes for batched drawing (much faster than one-by-one).
            # Mid-layer (slightly larger) for the dot-gain halo around dense dots.
            mid_ellipses = []
            # Main dots are fully opaque dark — they sit on top of the light canvas
            # so the underlying color isn't blended away.
            main_ellipses = []
            for ri in range(rows):
                for ci in range(cols):
                    r = int(radii[ri, ci])
                    cx = int(cx_base[ci] + offsets_x[ri, ci])
                    cy = int(cy_base[ri] + offsets_y[ri, ci])
                    if ratios[ri, ci] > 0.5:
                        # Halo slightly larger than the dot for a soft surround
                        mid_ellipses.append((cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1))
                    main_ellipses.append((cx - r, cy - r, cx + r, cy + r))

            # Batch draw: all halos first, then all main dots (fully opaque)
            for box in mid_ellipses:
                draw.ellipse(box, fill=mid_color)
            for box in main_ellipses:
                draw.ellipse(box, fill=dark)

            # Light color-tint of the original image stays underneath as a hint
            # of local color, kept very low so the dots still dominate.
            tinted = ImageOps.colorize(gray, black=dark, white=light)
            mixed = Image.blend(canvas, tinted, 0.08)

        mixed = ImageEnhance.Contrast(mixed).enhance(1.2)
        mixed = ImageEnhance.Color(mixed).enhance(1.1)

        # Add texture
        mixed = add_grain(mixed, strength=0.04, blur=0.1)
        mixed = apply_vignette(mixed, strength=0.2)

        return GenerationResult(
            title=f"Halftone: {asset.original_file_name or asset.id}",
            summary="Artistic halftone with varied dot pattern and depth.",
            image_bytes=save_png(mixed),
            generation_type="halftone",
            provider="local",
            model="pil+numpy",
            config={"cell_size": cell_size, "style": style, "palette": [list(dark), list(light)]},
            source_asset_ids=[asset.id],
        )
