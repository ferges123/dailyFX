from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png

# Blue tone presets (black, white)
_BLUE_TONES = {
    "classic": ((18, 44, 96), (228, 244, 255)),
    "deep": ((8, 28, 72), (180, 210, 240)),
    "light": ((40, 80, 140), (240, 250, 255)),
}


class CyanotypeModule:
    name = "cyanotype"
    label = "Cyanotype"
    description = "Blue-print toning with paper texture and adjustable tone."
    default_weight = 2
    default_config = {"tone": "classic", "texture": 0.12}
    config_schema = [
        {
            "key": "tone",
            "label": "Blue tone",
            "type": "select",
            "description": "Blue tone intensity (classic/deep/light).",
            "options": [
                {"value": "classic", "label": "Classic"},
                {"value": "deep", "label": "Deep"},
                {"value": "light", "label": "Light"},
            ],
            "default": "classic",
        },
        {
            "key": "texture",
            "label": "Paper texture",
            "type": "number",
            "description": "Paper texture strength (0.05 = subtle, 0.2 = heavy).",
            "min": 0.05,
            "max": 0.2,
            "step": 0.01,
            "default": 0.12,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)

        tone = config.get("tone", "classic")
        if tone not in _BLUE_TONES:
            tone = "classic"
        texture = max(0.05, min(0.2, float(config.get("texture", 0.12) or 0.12)))

        result = _apply_cyanotype(source, tone, texture)

        return GenerationResult(
            title=f"Cyanotype: {asset.original_file_name or asset.id}",
            summary="Blue-print toning with paper texture and adjustable tone.",
            image_bytes=save_png(result),
            generation_type="cyanotype",
            provider="local",
            model="pil",
            config={"tone": tone, "texture": texture},
            source_asset_ids=[asset.id],
        )


def _apply_cyanotype(img: Image.Image, tone: str, texture: float) -> Image.Image:
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray, cutoff=2)
    gray = ImageEnhance.Contrast(gray).enhance(1.3)
    gray = ImageEnhance.Sharpness(gray).enhance(1.2)

    # Apply blue tone
    black, white = _BLUE_TONES[tone]
    tint = ImageOps.colorize(gray, black=black, white=white)
    tint = ImageEnhance.Color(tint).enhance(1.2)

    # Multi-layer paper texture
    tint = add_grain(tint, strength=texture * 0.6, blur=0.15)
    tint = _add_paper_texture(tint, strength=texture * 0.4)

    # Vignette for aged look
    tint = apply_vignette(tint, strength=0.35)

    return tint


def _add_paper_texture(img: Image.Image, strength: float) -> Image.Image:
    """Add subtle paper fiber texture.

    Fibers are short line segments in 4 directions (0/45/90/135 degrees) to
    mimic the random weave of paper. We render onto an "L" mask and modulate
    the image's luminance subtly, so it acts as relief rather than tint.
    """
    import math
    import random

    w, h = img.size
    texture = Image.new("L", (w, h), 128)
    draw = ImageDraw.Draw(texture)

    # Density tuned to image area, capped to avoid huge draws on big images
    num_fibers = min(int(w * h * 0.0004), 20000)
    directions = (0.0, 45.0, 90.0, 135.0)
    for _ in range(num_fibers):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        length = random.randint(2, 8)
        angle = random.choice(directions)
        rad = math.radians(angle)
        x2 = x + int(length * math.cos(rad))
        y2 = y + int(length * math.sin(rad))
        # Slightly varying lightness (115..140) creates gentle relief
        fill = random.randint(115, 140)
        draw.line([(x, y), (x2, y2)], fill=fill, width=1)

    # Soften so fibers read as paper grain, not as visible strokes
    texture = texture.filter(ImageFilter.GaussianBlur(0.5))
    # Combine: convert texture to a luminance offset around mid-gray
    texture_rgb = Image.merge("RGB", (texture, texture, texture))
    # Screen with mid-gray keeps mid-tones unchanged, lifts/lowers based on fiber
    return Image.blend(img, ImageChops.screen(img, texture_rgb), strength)
