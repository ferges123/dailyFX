from __future__ import annotations

import random
from io import BytesIO

import numpy as np
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
            model="pil+numpy",
            config={"style": style, "palette": [list(dark), list(light)]},
            source_asset_ids=[asset.id],
        )


def _build_paper_cutout(
    source: Image.Image, dark: tuple[int, int, int], light: tuple[int, int, int], style: str
) -> bytes:
    size = (1200, 900)
    fitted = ImageOps.fit(source, size, centering=(0.5, 0.45))

    # Posterize the source for a flat color-block look (paper cuts are flat)
    poster = ImageOps.posterize(fitted, 5)
    poster = ImageEnhance.Color(poster).enhance(1.2)
    poster = ImageEnhance.Contrast(poster).enhance(1.3)
    poster = ImageEnhance.Sharpness(poster).enhance(1.2)

    if style == "textured":
        poster = add_grain(poster, strength=0.06, blur=0.0)

    # Build a soft alpha mask from a contrast-weighted grayscale. A hard
    # binary threshold (>110) produced jagged, aliased cut edges; using a
    # median-filtered grayscale with a smooth sigmoid gives a feathered
    # transition that reads as a real cut-paper edge.
    gray = ImageOps.grayscale(fitted)
    gray = ImageEnhance.Contrast(gray).enhance(1.4)
    gray = gray.filter(ImageFilter.MedianFilter(5))
    # Smooth sigmoid centered at 110 — produces a soft roll-off instead of
    # a single-pixel step cut.
    mask_arr = np.asarray(gray, dtype=np.float32)
    mask_arr = 255.0 / (1.0 + np.exp(-(mask_arr - 110.0) / 18.0))
    mask = Image.fromarray(mask_arr.astype(np.uint8), "L")

    # Soft cut edge (small blur) — keeps the cut crisp but not aliased.
    cut_mask = mask.filter(ImageFilter.GaussianBlur(radius=2))
    # Wider blur for the shadow falloff underneath.
    shadow_mask = mask.filter(ImageFilter.GaussianBlur(radius=15))

    # Rich textured paper background — fiber-like rather than uniform noise
    paper = Image.new("RGB", size, light)

    if style == "textured":
        # Multi-octave noise gives a paper-fiber feel (low-frequency
        # variation + high-frequency grain) instead of a single noise layer.
        paper = _add_paper_fibers(paper, light, density=0.10)
        # Subtle color variation toward the dark side for warmth
        tint = Image.new("RGB", size, tuple(int(c * 0.95) for c in light))
        paper = Image.blend(paper, tint, 0.15)

    # Multi-layer shadow for depth: a wider diffuse shadow + a tighter core
    shadow1_color = tuple(int(c * 0.4) for c in dark)
    shadow1 = Image.new("RGB", size, shadow1_color)
    shadow1 = ImageChops.offset(shadow1, 22, 22)
    paper = Image.composite(shadow1, paper, shadow_mask.point(lambda v: int(v * 0.45)))

    shadow2_color = tuple(int(c * 0.6) for c in dark)
    shadow2 = Image.new("RGB", size, shadow2_color)
    shadow2 = ImageChops.offset(shadow2, 8, 8)
    paper = Image.composite(shadow2, paper, shadow_mask.point(lambda v: int(v * 0.3)))

    # Apply the cutout using the SOFT mask (not the hard binary one). This
    # is the key fix — previously the hard mask created aliased edges that
    # betrayed the "paper cut" illusion.
    clipped = Image.new("RGB", size, light)
    clipped.paste(poster, (0, 0), cut_mask)
    paper = Image.composite(clipped, paper, cut_mask)

    # Final polish — gentle, not aggressive (autocontrast clipped=1 would
    # clip the soft shadow detail).
    paper = ImageEnhance.Sharpness(paper).enhance(1.15)

    # Subtle inner border for the "framed paper" feel
    if style == "textured":
        border = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(border)
        draw.rectangle((28, 28, size[0] - 29, size[1] - 29), outline=(*dark, 40), width=8)
        paper = Image.alpha_composite(paper.convert("RGBA"), border).convert("RGB")

    out = BytesIO()
    paper.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _add_paper_fibers(paper: Image.Image, base_color: tuple[int, int, int], density: float = 0.10) -> Image.Image:
    """Add a fiber-based paper texture (low + high frequency)."""
    w, h = paper.size
    # Low-frequency variation: large blurred noise (gives the paper uneven tone)
    low_freq = Image.effect_noise((w // 8, h // 8), 30).convert("L")
    low_freq = ImageOps.autocontrast(low_freq)
    low_freq = low_freq.resize((w, h), Image.Resampling.BICUBIC)
    low_freq = low_freq.filter(ImageFilter.GaussianBlur(radius=4))

    # High-frequency grain
    high_freq = Image.effect_noise((w, h), 15).convert("L")
    high_freq = ImageOps.autocontrast(high_freq)

    # Combine: base color + low-freq variation * density + subtle high-freq grain
    arr = np.asarray(paper, dtype=np.float32)
    low_dev = (np.asarray(low_freq, dtype=np.float32) - 128.0) * density
    high_dev = (np.asarray(high_freq, dtype=np.float32) - 128.0) * (density * 0.4)
    arr = arr + low_dev[:, :, None] + high_dev[:, :, None]
    return Image.fromarray(np.clip(arr, 0.0, 255.0).astype(np.uint8), "RGB")
