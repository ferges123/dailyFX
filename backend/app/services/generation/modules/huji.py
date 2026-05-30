from __future__ import annotations

import random
from datetime import datetime
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, get_font, load_rgb, save_png


class HujiModule:
    name = "huji"
    label = "Huji Cam"
    description = "Disposable film camera look — warm tones, light leaks, grain and date stamp."
    default_weight = 3
    default_config = {"date_stamp": "true"}
    config_schema = [
        {
            "key": "date_stamp",
            "label": "Date stamp",
            "type": "select",
            "options": [
                {"value": "true", "label": "On"},
                {"value": "false", "label": "Off"},
            ],
            "default": "true",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = random.choice(page_items)
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)
        date_stamp = str(config.get("date_stamp", "true")).lower() != "false"
        result = _apply_huji(source, asset.created_at, date_stamp)
        return GenerationResult(
            title=f"Huji: {asset.original_file_name or asset.id}",
            summary="Disposable film camera aesthetic with warm tones and light leaks.",
            image_bytes=result,
            generation_type="huji",
            provider="local",
            model="pil+huji",
            config={"date_stamp": date_stamp},
            source_asset_ids=[asset.id],
        )


def _apply_huji(source: Image.Image, created_at: str | None, date_stamp: bool) -> bytes:
    img = source.copy()
    w, h = img.size

    # 1. Warm color grade — lift shadows, push yellows/reds
    img = ImageEnhance.Color(img).enhance(1.1)
    img = ImageEnhance.Brightness(img).enhance(1.08)
    img = ImageEnhance.Contrast(img).enhance(0.85)

    # Warm tint overlay (orange-yellow cast)
    warm = Image.new("RGB", (w, h), (255, 200, 120))
    img = Image.blend(img, warm, 0.12)

    # Slightly fade blacks (lift shadows like expired film)
    img = _lift_shadows(img, lift=18)

    # 2. Light leak — top-right corner, warm orange/red
    leak_layer = Image.new("RGB", (w, h), (0, 0, 0))
    leak_draw = ImageDraw.Draw(leak_layer)
    # Primary leak: top-right
    leak_draw.ellipse(
        (int(w * 0.55), -int(h * 0.1), w + int(w * 0.1), int(h * 0.45)),
        fill=(255, 120, 40),
    )
    # Secondary leak: bottom-left edge
    leak_draw.ellipse(
        (-int(w * 0.1), int(h * 0.7), int(w * 0.35), h + int(h * 0.1)),
        fill=(255, 80, 20),
    )
    leak_layer = leak_layer.filter(ImageFilter.GaussianBlur(radius=int(min(w, h) * 0.18)))
    img = ImageChops.screen(img, leak_layer)

    # 3. Vignette
    img = apply_vignette(img, strength=0.38)

    # 4. Grain
    img = add_grain(img, strength=0.09, blur=0.3)

    # 5. Slight warm blur (cheap lens softness)
    soft = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    img = Image.blend(img, soft, 0.25)

    # 6. Date stamp — bottom right, red LCD-style font
    if date_stamp:
        date_str = _format_date(created_at)
        if date_str:
            img = _draw_date_stamp(img, date_str)

    return save_png(img)


def _lift_shadows(img: Image.Image, lift: int = 18) -> Image.Image:
    """Lift shadow values to simulate faded/expired film."""
    lut = [min(255, i + lift) for i in range(256)]
    r, g, b = img.split()
    r = r.point(lut)
    g = g.point([min(255, i + lift - 4) for i in range(256)])  # slightly less green lift
    b = b.point([min(255, i + lift - 8) for i in range(256)])  # even less blue lift
    return Image.merge("RGB", (r, g, b))


def _draw_date_stamp(img: Image.Image, date_str: str) -> Image.Image:
    w, h = img.size
    font_size = max(16, int(h * 0.022))
    font = get_font("Inter-Regular", font_size)
    margin = int(h * 0.025)

    # Draw on separate layer then blur slightly — simulates ink bleed on film
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.text((w - margin, h - margin), date_str, fill=(255, 245, 220, 210), font=font, anchor="rb")
    layer = layer.filter(ImageFilter.GaussianBlur(radius=0.8))

    img = img.convert("RGBA")
    img = Image.alpha_composite(img, layer)
    return img.convert("RGB")


def _format_date(created_at: str | None) -> str:
    if not isinstance(created_at, str):
        return ""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return dt.strftime("%m ' %y")
    except ValueError:
        return ""
