from __future__ import annotations

from datetime import datetime
from io import BytesIO

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, get_font, load_rgb


class PolaroidModule:
    name = "polaroid"
    label = "Polaroid"
    description = "Classic instant-film frame with high-legibility typography."
    default_weight = 1
    default_config = {"style": "modern"}
    config_schema = [
        {
            "key": "style",
            "label": "Style",
            "type": "select",
            "description": "Polaroid style (modern/vintage).",
            "options": [
                {"value": "modern", "label": "Modern"},
                {"value": "vintage", "label": "Vintage"},
            ],
            "default": "modern",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)
        style = config.get("style", "modern")
        if style not in ("modern", "vintage"):
            style = "modern"
        framed = _build_polaroid(source, asset.created_at, asset.original_file_name or asset.id, style)

        return GenerationResult(
            title=f"Polaroid: {asset.original_file_name or asset.id}",
            summary="Instant-film frame with massive, readable typography.",
            image_bytes=framed,
            generation_type="polaroid",
            provider="local",
            model="pil+custom_fonts_v2",
            config={"style": style},
            source_asset_ids=[asset.id],
        )


def _build_polaroid(source: Image.Image, created_at: str | None, caption: str, style: str) -> bytes:
    # 1. Base Dimensions - preserve aspect ratio of source
    canvas_w = 1400
    border_side = 100  # left/right margin inside canvas
    photo_w = canvas_w - 2 * border_side

    src_w, src_h = source.size
    photo_h = int(photo_w * src_h / src_w)

    # Bottom area for text: fixed height
    bottom_area = 380
    canvas_h = 100 + photo_h + bottom_area  # top_margin + photo + text area

    # 2. Image Prep - style-dependent (crop to exact photo_w × photo_h)
    photo = ImageOps.fit(source, (photo_w, photo_h), centering=(0.5, 0.45))

    if style == "vintage":
        # Vintage: warmer, faded, more grain
        photo = ImageEnhance.Color(photo).enhance(0.85)
        photo = ImageEnhance.Contrast(photo).enhance(0.88)
        photo = ImageEnhance.Brightness(photo).enhance(1.08)
        photo = apply_vignette(photo, strength=0.35)
        photo = add_grain(photo, strength=0.08)
    else:
        # Modern: cleaner, sharper
        photo = ImageEnhance.Color(photo).enhance(1.15)
        photo = ImageEnhance.Contrast(photo).enhance(0.95)
        photo = ImageEnhance.Brightness(photo).enhance(1.02)
        photo = apply_vignette(photo, strength=0.25)
        photo = add_grain(photo, strength=0.04)

    # 3. Canvas Setup - style-dependent background
    if style == "vintage":
        canvas = Image.new("RGB", (canvas_w, canvas_h), (242, 238, 228))  # Aged cream
    else:
        canvas = Image.new("RGB", (canvas_w, canvas_h), (248, 246, 242))  # Off-white

    draw = ImageDraw.Draw(canvas)

    # 4. Placement & Shadow
    photo_x = (canvas_w - photo_w) // 2
    photo_y = 100

    # Soft deep shadow
    _draw_shadow(canvas, (photo_x - 15, photo_y + 15), (photo_w + 30, photo_h + 30))
    canvas.paste(photo, (photo_x, photo_y))

    # 5. Typography - ADAPTIVE SCALING (V6)
    # Adjust font size based on caption length to prevent overflow
    base_size_factor = 0.035  # Reduced further from 0.045
    if len(caption) > 20:
        base_size_factor = 0.030
    if len(caption) > 30:
        base_size_factor = 0.025

    size_main = int(canvas_h * base_size_factor)
    size_date = int(canvas_h * 0.012)  # Reduced from 0.016

    font_main = get_font("PlayfairDisplay-Medium", size_main)
    font_date = get_font("Inter-Regular", size_date)

    date_label = _format_date(created_at)

    # Text colors - style-dependent
    if style == "vintage":
        text_color = (60, 50, 40)
        date_color = (140, 125, 105)
    else:
        text_color = (35, 32, 28)
        date_color = (120, 110, 100)

    # Position text with balanced margin
    text_y = photo_y + photo_h + int(canvas_h * 0.06)

    # Truncate caption if still too long after scaling
    display_caption = caption[:40] + "..." if len(caption) > 40 else caption

    # Draw Text (Title) - Use explicit anchor for positioning
    draw.text((photo_x + int(canvas_w * 0.05), text_y), display_caption, fill=text_color, font=font_main, anchor="lt")

    # Measure title to place date accurately below it
    m_bbox = draw.textbbox((photo_x + int(canvas_w * 0.05), text_y), display_caption, font=font_main, anchor="lt")
    main_bottom = m_bbox[3]

    # Draw Date (with explicit gap relative to main text bottom)
    if date_label:
        date_gap = int(size_main * 0.4)
        draw.text(
            (photo_x + int(canvas_w * 0.05), main_bottom + date_gap),
            date_label,
            fill=date_color,
            font=font_date,
            anchor="lt",
        )

    # 6. Final Texture (Subtle paper fiber) - stronger for vintage
    texture = Image.effect_noise((canvas_w, canvas_h), 10).convert("L")
    if style == "vintage":
        texture = ImageOps.colorize(texture, black=(235, 230, 215), white=(255, 255, 250))
        canvas = Image.blend(canvas, texture, 0.25)
    else:
        texture = ImageOps.colorize(texture, black=(242, 240, 235), white=(255, 255, 255))
        canvas = Image.blend(canvas, texture, 0.15)

    out = BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _draw_shadow(canvas: Image.Image, offset: tuple[int, int], size: tuple[int, int]) -> None:
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer = Image.new("RGBA", size, (10, 10, 10, 80))  # Lighter, larger blur
    shadow.paste(layer, offset)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=40))
    canvas.paste(shadow.convert("RGB"), (0, 0), shadow.split()[-1])


def _format_date(created_at: str | None) -> str:
    if not isinstance(created_at, str):
        return ""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return dt.strftime("%B %d, %Y").upper()
