from __future__ import annotations

import random
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
        
        # Create varied halftone dots
        for y in range(0, height, cell_size):
            for x in range(0, width, cell_size):
                sample = gray.crop((x, y, min(x + cell_size, width), min(y + cell_size, height)))
                value = sample.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
                ratio = max(0.1, 1.0 - value / 255.0)
                
                # Varied dot sizes for organic look
                if style == "varied":
                    jitter = random.uniform(0.85, 1.15)
                    radius = max(1, int((cell_size / 2.2) * ratio * jitter))
                    cx = x + cell_size // 2 + random.randint(-2, 2)
                    cy = y + cell_size // 2 + random.randint(-2, 2)
                else:
                    radius = max(1, int((cell_size / 2.2) * ratio))
                    cx = x + cell_size // 2
                    cy = y + cell_size // 2
                
                # Gradient dots for depth
                if ratio > 0.5:
                    mid_color = tuple(int(dark[i] * 0.7 + light[i] * 0.3) for i in range(3))
                    draw.ellipse((cx - radius - 1, cy - radius - 1, cx + radius + 1, cy + radius + 1), fill=mid_color)
                
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=dark)

        # Blend with colorized version for richness
        overlay = ImageOps.colorize(gray, black=dark, white=light)
        mixed = Image.blend(canvas, overlay, 0.25)
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
            model="pil",
            config={"cell_size": cell_size, "style": style, "palette": [list(dark), list(light)]},
            source_asset_ids=[asset.id],
        )
