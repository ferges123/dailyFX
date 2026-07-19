from __future__ import annotations

import random
from datetime import datetime

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, get_font, load_rgb, save_png

# Random leak positions like a real disposable camera — every shot is different.
_LEAK_ORIGINS = [
    (0.85, 0.10),  # top-right
    (0.12, 0.85),  # bottom-left
    (0.90, 0.85),  # bottom-right
    (0.10, 0.15),  # top-left
    (0.50, 0.05),  # top-center
    (0.92, 0.50),  # right edge
]


class HujiModule:
    name = "huji"
    label = "Huji Cam"
    description = "Disposable film camera look — warm tones, light leaks, grain and date stamp."
    default_weight = 3
    default_config = {"date_stamp": True}
    config_schema = [
        {
            "key": "date_stamp",
            "label": "Date stamp",
            "type": "boolean",
            "default": True,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = random.choice(page_items)
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)
        date_stamp = config.get("date_stamp", True)
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

    # Lift shadows with a sigmoidal curve instead of a linear offset.
    # A linear `+lift` pushes whites toward clipping and raises midtones
    # uniformly; a sigmoidal curve lifts only the shadows and keeps
    # midtones/highlights intact, which is what expired film actually does.
    arr = np.asarray(img, dtype=np.uint8).copy()
    shadow_lut = _shadow_lift_lut(0.10)
    arr = shadow_lut[arr]
    img = Image.fromarray(arr, "RGB")

    # 2. Light leak — random origin each run, built from a smooth radial
    # gradient (numpy) rather than a blurred ellipse, for a more organic look.
    ox_frac, oy_frac = random.choice(_LEAK_ORIGINS)
    ox = ox_frac * w + random.randint(-w // 12, w // 12)
    oy = oy_frac * h + random.randint(-h // 12, h // 12)
    ox = max(0, min(w - 1, int(ox)))
    oy = max(0, min(h - 1, int(oy)))
    primary = (255, 120, 40)
    secondary = (255, 80, 20)
    leak = _build_leak_layer(w, h, ox, oy, primary, secondary)
    img = ImageChops.screen(img, leak)

    # 3. Vignette
    img = apply_vignette(img, strength=0.38)

    # 4. Grain
    img = add_grain(img, strength=0.09, blur=0.3)

    # 5. Slight warm blur (cheap lens softness)
    soft = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    img = Image.blend(img, soft, 0.25)

    # 6. Date stamp — bottom right, orange/red LCD-style font (Huji app look)
    if date_stamp:
        date_str = _format_date(created_at)
        if date_str:
            img = _draw_date_stamp(img, date_str)

    return save_png(img)


def _build_leak_layer(w: int, h: int, cx: int, cy: int, primary: tuple, secondary: tuple) -> Image.Image:
    """Build a soft, organic light leak from two radial gradients.

    Uses a normalized radial distance with a gamma curve so the falloff is
    smoother than a single blurred ellipse (which produces a hard blob).
    """
    y_idx, x_idx = np.ogrid[:h, :w]
    dx = (x_idx - cx) / w
    dy = (y_idx - cy) / h
    dist = np.sqrt(dx * dx + dy * dy)
    # Soft falloff: stronger near origin, long tail into the frame
    primary_alpha = np.clip(1.0 - dist / 0.55, 0.0, 1.0) ** 1.8
    # Tighter, brighter accent near the leak origin
    accent_alpha = np.clip(1.0 - dist / 0.30, 0.0, 1.0) ** 2.5

    arr = np.zeros((h, w, 3), dtype=np.float32)
    for i in range(3):
        arr[..., i] = primary[i] * primary_alpha + secondary[i] * accent_alpha * 0.6
    arr = arr.clip(0.0, 255.0).astype(np.uint8)
    leak = Image.fromarray(arr, "RGB")
    # Slight blur to blend edges smoothly with the underlying image
    return leak.filter(ImageFilter.GaussianBlur(radius=max(w, h) * 0.04))


def _shadow_lift_lut(lift: float) -> np.ndarray:
    """Lift shadows via a sigmoidal curve that leaves highlights untouched."""
    x = np.arange(256, dtype=np.float32) / 255.0
    shadow_mask = np.clip(1.0 - x * 2.0, 0.0, 1.0) ** 1.4
    lifted = x + lift * shadow_mask * (1.0 - x) * 3.0
    return np.clip(lifted * 255.0, 0.0, 255.0).astype(np.uint8)


def _draw_date_stamp(img: Image.Image, date_str: str) -> Image.Image:
    w, h = img.size
    font_size = max(16, int(h * 0.022))
    font = get_font("Inter-Regular", font_size)
    margin = int(h * 0.025)

    # Draw on separate layer then blur slightly — simulates ink bleed on film
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    # Classic Huji app: bright orange-red date stamp, semi-transparent
    draw.text((w - margin, h - margin), date_str, fill=(255, 80, 50, 220), font=font, anchor="rb")
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
