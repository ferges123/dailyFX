from __future__ import annotations

import random
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, load_rgb, select_palette


class PaperCutoutModule:
    name = "paper_cutout"
    label = "Paper Cutout"
    description = "Layered paper cutout with rich texture and depth."
    default_weight = 2
    default_config = {"style": "textured"}
    config_schema = [
        {
            "key": "style",
            "label": "Style",
            "type": "select",
            "description": "Paper style.",
            "options": [
                {"value": "textured", "label": "Textured (rich)"},
                {"value": "clean", "label": "Clean (minimal)"},
            ],
            "default": "textured",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = random.choice(page_items)
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)
        dark, light = select_palette(config)
        style = config.get("style", "textured")
        result = _build_paper_cutout(source, dark, light, style)

        return GenerationResult(
            title=f"Paper Cutout: {asset.original_file_name or asset.id}",
            summary="Layered paper cutout with rich texture and depth.",
            image_bytes=result,
            generation_type="paper_cutout",
            provider="local",
            model="pil",
            config={"style": style, "palette": [list(dark), list(light)]},
            source_asset_ids=[asset.id],
        )


def _build_paper_cutout(
    source: Image.Image, dark: tuple[int, int, int], light: tuple[int, int, int], style: str
) -> bytes:
    size = (1200, 900)
    fitted = ImageOps.fit(source, size, centering=(0.5, 0.45))

    # Enhanced posterization with more levels
    poster = ImageOps.posterize(fitted, 5)
    poster = ImageEnhance.Color(poster).enhance(1.2)
    poster = ImageEnhance.Contrast(poster).enhance(1.3)
    poster = ImageEnhance.Sharpness(poster).enhance(1.2)

    if style == "textured":
        poster = add_grain(poster, strength=0.06, blur=0.0)

    # Better mask with edge detection
    gray = ImageOps.grayscale(fitted)
    gray = ImageEnhance.Contrast(gray).enhance(1.4)
    mask = gray.filter(ImageFilter.MedianFilter(5)).point(lambda value: 255 if value > 110 else 0)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=2))

    # Rich textured paper background
    paper = Image.new("RGB", size, light)

    if style == "textured":
        # Multiple texture layers for depth
        texture1 = Image.effect_noise(size, 15).convert("L")
        texture2 = Image.effect_noise(size, 25).convert("L")
        texture1 = ImageOps.autocontrast(texture1)
        texture2 = ImageOps.autocontrast(texture2)

        texture_rgb1 = Image.merge("RGB", (texture1, texture1, texture1))
        texture_rgb2 = Image.merge("RGB", (texture2, texture2, texture2))

        paper = Image.blend(paper, texture_rgb1, 0.12)
        paper = Image.blend(paper, texture_rgb2, 0.06)

        # Add subtle color variation
        tint = Image.new("RGB", size, tuple(int(c * 0.95) for c in light))
        paper = Image.blend(paper, tint, 0.15)

    # Multi-layer shadow for depth
    shadow_mask = mask.filter(ImageFilter.GaussianBlur(radius=15))
    shadow1 = Image.new("RGB", size, tuple(int(c * 0.4) for c in dark))
    shadow1 = ImageChops.offset(shadow1, 22, 22)
    paper = Image.composite(shadow1, paper, shadow_mask.point(lambda value: int(value * 0.45)))

    # Closer shadow for definition
    shadow2 = Image.new("RGB", size, tuple(int(c * 0.6) for c in dark))
    shadow2 = ImageChops.offset(shadow2, 8, 8)
    paper = Image.composite(shadow2, paper, shadow_mask.point(lambda value: int(value * 0.3)))

    # Apply cutout
    clipped = Image.new("RGB", size, light)
    clipped.paste(poster, (0, 0), mask)
    paper = Image.composite(clipped, paper, mask)

    # Enhance final result
    paper = ImageOps.autocontrast(paper, cutoff=1)
    paper = ImageEnhance.Sharpness(paper).enhance(1.15)

    # Subtle border
    if style == "textured":
        border = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(border)
        draw.rectangle((28, 28, size[0] - 29, size[1] - 29), outline=(*dark, 40), width=8)
        paper = Image.alpha_composite(paper.convert("RGBA"), border).convert("RGB")

    out = BytesIO()
    paper.save(out, format="PNG", optimize=True)
    return out.getvalue()
