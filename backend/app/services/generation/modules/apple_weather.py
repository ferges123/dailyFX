from __future__ import annotations

import logging
from datetime import UTC, datetime

from PIL import Image, ImageDraw, ImageFilter

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import get_font, load_rgb, save_png
from app.services.generation.modules.instaweather import (
    fetch_weather,
    get_fallback_weather,
    get_text_height,
    get_text_size,
    map_wmo_code,
    parse_date,
    reverse_geocode,
)

logger = logging.getLogger(__name__)


def _weather_theme(weather_code: int) -> tuple[tuple[int, int, int], tuple[int, int, int, int]]:
    if weather_code == 0:
        return (255, 214, 102), (20, 24, 34, 134)
    if weather_code in (1, 2, 3, 45, 48):
        return (182, 196, 212), (16, 20, 28, 138)
    if weather_code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return (126, 182, 255), (14, 18, 28, 142)
    if weather_code in (71, 73, 75, 77, 85, 86):
        return (216, 232, 255), (17, 20, 28, 138)
    if weather_code in (95, 96, 99):
        return (255, 189, 112), (22, 18, 26, 146)
    return (184, 196, 212), (16, 20, 28, 138)


async def _resolve_context(asset, client) -> tuple[datetime, str | None, dict]:
    exif_info = await client.get_asset_exif(asset.id)
    lat = exif_info.get("latitude")
    lon = exif_info.get("longitude")
    taken_str = exif_info.get("dateTimeOriginal") or asset.created_at
    dt = parse_date(taken_str) or datetime.now(UTC)

    location = None
    weather_info = None

    try:
        if (lat not in (None, "")) and (lon not in (None, "")):
            lat_f = float(lat)
            lon_f = float(lon)
            location = await reverse_geocode(lat_f, lon_f)
            if not location:
                location = f"{abs(lat_f):.2f}°{'N' if lat_f >= 0 else 'S'}, {abs(lon_f):.2f}°{'E' if lon_f >= 0 else 'W'}"
            weather_info = await fetch_weather(lat_f, lon_f, dt)
            if not weather_info:
                weather_info = get_fallback_weather(lat_f, dt.month)
        else:
            # No GPS metadata on the asset; keep the card anonymous but still render weather.
            weather_info = await fetch_weather(0.0, 0.0, dt)
            if not weather_info:
                weather_info = get_fallback_weather(0.0, dt.month)
    except Exception as exc:
        logger.warning("Metadata fetch failed for Apple Weather: %s", exc)
        if not weather_info:
            weather_info = get_fallback_weather(0.0, dt.month)

    return dt, location, weather_info


class AppleWeatherModule:
    name = "apple_weather"
    label = "Apple Weather"
    description = "Apple-style weather card with frosted glass, clean typography, and soft atmospheric accents."
    default_weight = 2
    default_config = {
        "units": "celsius",
        "protect_faces": "true",
    }
    config_schema = [
        {
            "key": "units",
            "label": "Temperature Unit",
            "type": "select",
            "description": "Units to show temperature.",
            "options": [
                {"value": "celsius", "label": "Celsius (°C)"},
                {"value": "fahrenheit", "label": "Fahrenheit (°F)"},
            ],
            "default": "celsius",
        },
        {
            "key": "protect_faces",
            "label": "Face protection",
            "type": "select",
            "description": "Shift the card to avoid detected faces.",
            "options": [
                {"value": "true", "label": "Enabled"},
                {"value": "false", "label": "Disabled"},
            ],
            "default": "true",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        img = load_rgb(image_bytes)

        dt, location, weather_info = await _resolve_context(asset, client)

        faces = []
        try:
            asset_info = await client.get_asset_info(asset.id)
            raw_people = asset_info.get("people") or []
            for person_payload in raw_people:
                raw_faces = (
                    person_payload.get("faces")
                    or person_payload.get("faceList")
                    or person_payload.get("face")
                    or []
                )
                if isinstance(raw_faces, list):
                    for face_payload in raw_faces:
                        face = client._coerce_face_summary(face_payload)
                        if face:
                            faces.append(face)
                elif isinstance(raw_faces, dict):
                    face = client._coerce_face_summary(raw_faces)
                    if face:
                        faces.append(face)
        except Exception as exc:
            logger.warning("Failed to load asset faces for Apple Weather: %s", exc)

        units = config.get("units", "celsius")
        protect_faces = str(config.get("protect_faces", "true")).lower() == "true"

        layout_position = "bottom_left"
        if protect_faces and faces:
            width, height = img.size
            scale = min(width, height) / 1000.0
            margin = int(38 * scale)
            card_width_est = int(520 * scale)
            card_height_est = int(335 * scale)
            positions_map = {
                "bottom_left": (margin, height - margin - card_height_est, margin + card_width_est, height - margin),
                "bottom_right": (width - margin - card_width_est, height - margin - card_height_est, width - margin, height - margin),
                "top_left": (margin, margin, margin + card_width_est, margin + card_height_est),
                "top_right": (width - margin - card_width_est, margin, width - margin, margin + card_height_est),
            }

            for candidate in ("bottom_left", "bottom_right", "top_left", "top_right"):
                ox1, oy1, ox2, oy2 = positions_map[candidate]
                collision = False
                for face in faces:
                    if (
                        face.bounding_box_x1 is not None
                        and face.bounding_box_y1 is not None
                        and face.bounding_box_x2 is not None
                        and face.bounding_box_y2 is not None
                    ):
                        fx1 = int(face.bounding_box_x1 * width)
                        fy1 = int(face.bounding_box_y1 * height)
                        fx2 = int(face.bounding_box_x2 * width)
                        fy2 = int(face.bounding_box_y2 * height)
                        if fx1 < ox2 and fx2 > ox1 and fy1 < oy2 and fy2 > oy1:
                            collision = True
                            break
                if not collision:
                    layout_position = candidate
                    break

        result_img = _draw_apple_weather_overlay(
            img,
            weather_info=weather_info,
            location=location,
            dt=dt,
            layout_position=layout_position,
            units=units,
        )

        temp_val = weather_info["temp_c"]
        temp_str = f"{int(temp_val)}°C" if units == "celsius" else f"{int((temp_val * 9 / 5) + 32)}°F"
        weather_desc, _ = map_wmo_code(weather_info["weather_code"])
        loc_str = f" in {location}" if location else ""

        return GenerationResult(
            title=f"Apple Weather: {asset.original_file_name or asset.id}",
            summary=f"Applied Apple Weather overlay. Weather: {weather_desc}, {temp_str}{loc_str}.",
            image_bytes=save_png(result_img),
            generation_type=self.name,
            provider="local",
            model="pil",
            config={
                "units": units,
                "protect_faces": protect_faces,
                "resolved_position": layout_position,
                "mode": "apple_weather",
            },
            source_asset_ids=[asset.id],
        )


def _draw_weather_icon(draw: ImageDraw.ImageDraw, cx: float, cy: float, size: float, weather_code: int, scale: float):
    x = cx - size / 2
    y = cy - size / 2

    # 0 = Clear sky
    if weather_code == 0:
        # Sun center
        draw.ellipse([x + size * 0.25, y + size * 0.25, x + size * 0.75, y + size * 0.75], fill=(255, 204, 0))
        # Outer glow rings
        draw.ellipse([x + size * 0.15, y + size * 0.15, x + size * 0.85, y + size * 0.85], outline=(255, 220, 100, 60), width=max(1, int(2 * scale)))
        draw.ellipse([x + size * 0.05, y + size * 0.05, x + size * 0.95, y + size * 0.95], outline=(255, 220, 100, 30), width=max(1, int(1 * scale)))

    # 1, 2 = Partly cloudy
    elif weather_code in (1, 2):
        # Sun peaking out behind the cloud
        sun_cx = cx + size * 0.15
        sun_cy = cy - size * 0.15
        sun_r = size * 0.20
        draw.ellipse([sun_cx - sun_r, sun_cy - sun_r, sun_cx + sun_r, sun_cy + sun_r], fill=(255, 204, 0))
        draw.ellipse([sun_cx - sun_r - size*0.06, sun_cy - sun_r - size*0.06, sun_cx + sun_r + size*0.06, sun_cy + sun_r + size*0.06], outline=(255, 220, 100, 40), width=max(1, int(1 * scale)))

        # Soft layered cloud
        # Back cloud puff (darker/gray)
        draw.ellipse([cx - size * 0.22, cy - size * 0.05, cx + size * 0.10, cy + size * 0.27], fill=(185, 195, 215))
        # Front cloud puffs (white)
        draw.ellipse([cx - size * 0.35, cy + size * 0.02, cx - size * 0.08, cy + size * 0.29], fill=(255, 255, 255))
        draw.ellipse([cx + size * 0.02, cy + size * 0.06, cx + size * 0.26, cy + size * 0.30], fill=(255, 255, 255))
        draw.ellipse([cx - size * 0.18, cy - size * 0.14, cx + size * 0.18, cy + size * 0.22], fill=(255, 255, 255))
        # Bottom connection pill
        draw.rounded_rectangle([cx - size * 0.35, cy + size * 0.14, cx + size * 0.26, cy + size * 0.30], radius=max(1, int(8 * scale)), fill=(255, 255, 255))

    # 3 = Cloudy, 45, 48 = Foggy
    elif weather_code in (3, 45, 48):
        # Back cloud (bluish gray)
        draw.ellipse([cx - size * 0.18, cy - size * 0.16, cx + size * 0.22, cy + size * 0.24], fill=(160, 175, 195))
        draw.ellipse([cx - size * 0.30, cy - size * 0.02, cx, cy + size * 0.28], fill=(160, 175, 195))
        # Front cloud (white)
        draw.ellipse([cx - size * 0.34, cy + size * 0.04, cx - size * 0.08, cy + size * 0.30], fill=(245, 247, 250))
        draw.ellipse([cx + size * 0.02, cy + size * 0.08, cx + size * 0.28, cy + size * 0.34], fill=(245, 247, 250))
        draw.ellipse([cx - size * 0.18, cy - size * 0.10, cx + size * 0.18, cy + size * 0.26], fill=(255, 255, 255))
        draw.rounded_rectangle([cx - size * 0.34, cy + size * 0.16, cx + size * 0.28, cy + size * 0.34], radius=max(1, int(9 * scale)), fill=(255, 255, 255))

        # Fog lines for 45, 48
        if weather_code in (45, 48):
            draw.rounded_rectangle([cx - size * 0.38, cy + size * 0.38, cx + size * 0.38, cy + size * 0.42], radius=max(1, int(2 * scale)), fill=(255, 255, 255, 160))
            draw.rounded_rectangle([cx - size * 0.28, cy + size * 0.46, cx + size * 0.28, cy + size * 0.50], radius=max(1, int(2 * scale)), fill=(255, 255, 255, 120))

    # 51, 53, 55 = Drizzle, 56, 57 = Freezing drizzle, 61, 63, 65 = Rain, 66, 67 = Freezing rain, 80, 81, 82 = Rain showers
    elif weather_code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        # Dark rain cloud
        # Back puff
        draw.ellipse([cx - size * 0.18, cy - size * 0.18, cx + size * 0.22, cy + size * 0.22], fill=(110, 125, 145))
        draw.ellipse([cx - size * 0.30, cy - size * 0.04, cx, cy + size * 0.26], fill=(110, 125, 145))
        # Front puff
        draw.ellipse([cx - size * 0.34, cy + size * 0.02, cx - size * 0.08, cy + size * 0.28], fill=(180, 195, 215))
        draw.ellipse([cx + size * 0.02, cy + size * 0.06, cx + size * 0.28, cy + size * 0.32], fill=(180, 195, 215))
        draw.ellipse([cx - size * 0.18, cy - size * 0.12, cx + size * 0.18, cy + size * 0.24], fill=(200, 215, 235))
        draw.rounded_rectangle([cx - size * 0.34, cy + size * 0.14, cx + size * 0.28, cy + size * 0.32], radius=max(1, int(8 * scale)), fill=(200, 215, 235))

        # Raindrops (3 slanted lines)
        drop_color = (100, 185, 255, 230)
        draw.line([cx - size * 0.18, cy + size * 0.36, cx - size * 0.22, cy + size * 0.48], fill=drop_color, width=max(1, int(2.5 * scale)))
        draw.line([cx, cy + size * 0.36, cx - size * 0.04, cy + size * 0.48], fill=drop_color, width=max(1, int(2.5 * scale)))
        draw.line([cx + size * 0.18, cy + size * 0.36, cx + size * 0.14, cy + size * 0.48], fill=drop_color, width=max(1, int(2.5 * scale)))

    # 71, 73, 75, 77 = Snowfall, 85, 86 = Snow showers
    elif weather_code in (71, 73, 75, 77, 85, 86):
        # Soft winter cloud
        # Back puff
        draw.ellipse([cx - size * 0.18, cy - size * 0.16, cx + size * 0.22, cy + size * 0.24], fill=(160, 175, 195))
        # Front puff
        draw.ellipse([cx - size * 0.34, cy + size * 0.04, cx - size * 0.08, cy + size * 0.30], fill=(220, 225, 235))
        draw.ellipse([cx + size * 0.02, cy + size * 0.08, cx + size * 0.28, cy + size * 0.34], fill=(220, 225, 235))
        draw.ellipse([cx - size * 0.18, cy - size * 0.10, cx + size * 0.18, cy + size * 0.26], fill=(235, 240, 248))
        draw.rounded_rectangle([cx - size * 0.34, cy + size * 0.16, cx + size * 0.28, cy + size * 0.34], radius=max(1, int(8 * scale)), fill=(235, 240, 248))

        # Snowflakes (3 white dots)
        snow_color = (255, 255, 255, 240)
        draw.ellipse([cx - size * 0.20, cy + size * 0.38, cx - size * 0.12, cy + size * 0.46], fill=snow_color)
        draw.ellipse([cx - size * 0.04, cy + size * 0.40, cx + size * 0.04, cy + size * 0.48], fill=snow_color)
        draw.ellipse([cx + size * 0.12, cy + size * 0.38, cx + size * 0.20, cy + size * 0.46], fill=snow_color)

    # 95, 96, 99 = Thunderstorm
    elif weather_code in (95, 96, 99):
        # Storm cloud
        # Back puff
        draw.ellipse([cx - size * 0.18, cy - size * 0.20, cx + size * 0.22, cy + size * 0.20], fill=(70, 75, 95))
        draw.ellipse([cx - size * 0.30, cy - size * 0.06, cx, cy + size * 0.24], fill=(70, 75, 95))
        # Front puff
        draw.ellipse([cx - size * 0.34, cy + size * 0.00, cx - size * 0.08, cy + size * 0.26], fill=(100, 105, 130))
        draw.ellipse([cx + size * 0.02, cy + size * 0.04, cx + size * 0.28, cy + size * 0.30], fill=(100, 105, 130))
        draw.ellipse([cx - size * 0.18, cy - size * 0.14, cx + size * 0.18, cy + size * 0.22], fill=(120, 125, 150))
        draw.rounded_rectangle([cx - size * 0.34, cy + size * 0.12, cx + size * 0.28, cy + size * 0.30], radius=max(1, int(8 * scale)), fill=(120, 125, 150))

        # Lightning bolt peaking out
        bolt_pts = [
            (cx + size * 0.08, cy + size * 0.26),
            (cx - size * 0.12, cy + size * 0.46),
            (cx - size * 0.02, cy + size * 0.46),
            (cx - size * 0.14, cy + size * 0.66),
            (cx + size * 0.12, cy + size * 0.40),
            (cx + size * 0.02, cy + size * 0.40)
        ]
        draw.polygon(bolt_pts, fill=(255, 215, 0))

    else:
        # Fallback glowing sun
        draw.ellipse([cx - size * 0.25, cy - size * 0.25, cx + size * 0.25, cy + size * 0.25], fill=(255, 204, 0))


def _weather_gradient(weather_code: int) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    # Returns (top_color, bottom_color, accent_color)
    if weather_code == 0:
        return (50, 130, 230), (120, 190, 255), (255, 214, 102)
    elif weather_code in (1, 2):
        return (70, 115, 180), (130, 170, 215), (182, 196, 212)
    elif weather_code in (3, 45, 48):
        return (90, 105, 125), (145, 160, 180), (184, 196, 212)
    elif weather_code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return (40, 55, 80), (90, 110, 135), (126, 182, 255)
    elif weather_code in (71, 73, 75, 77, 85, 86):
        return (100, 125, 150), (180, 200, 220), (216, 232, 255)
    elif weather_code in (95, 96, 99):
        return (20, 25, 45), (55, 60, 90), (255, 189, 112)
    return (70, 115, 180), (130, 170, 215), (184, 196, 212)


def _draw_apple_weather_overlay(
    img: Image.Image,
    weather_info: dict,
    location: str | None,
    dt: datetime,
    layout_position: str,
    units: str,
) -> Image.Image:
    width, height = img.size
    scale = min(width, height) / 1000.0

    temp_val = weather_info["temp_c"]
    if units == "fahrenheit":
        temp_val = (temp_val * 9 / 5) + 32
        temp_str = f"{int(temp_val)}°F"
    else:
        temp_str = f"{int(temp_val)}°C"

    weather_desc, _ = map_wmo_code(weather_info["weather_code"])
    accent_rgb, panel_fill = _weather_theme(weather_info["weather_code"])

    font_location = get_font("Inter-Regular", max(11, int(13 * scale)))
    font_temp = get_font("Inter-Regular", max(68, int(84 * scale)))
    font_desc = get_font("Inter-Regular", max(20, int(23 * scale)))
    font_meta = get_font("Inter-Regular", max(12, int(13 * scale)))

    temp_img = Image.new("RGBA", (100, 100))
    temp_draw = ImageDraw.Draw(temp_img)

    location_text = (location or "NO GPS").upper()
    date_text = dt.strftime("%A • %B %d • %Y").upper()
    condition_text = weather_desc.upper()

    location_w, location_h = get_text_size(location_text, font_location, temp_draw)
    temp_w, _ = get_text_size(temp_str, font_temp, temp_draw)
    temp_h = get_text_height(temp_str, font_temp, temp_draw)
    condition_w, condition_h = get_text_size(condition_text, font_desc, temp_draw)
    meta_w, meta_h = get_text_size(date_text, font_meta, temp_draw)

    card_padding = int(24 * scale)
    outer_gap = int(14 * scale)
    row_gap = int(10 * scale)
    icon_gap = int(14 * scale)
    chip_pad_x = int(10 * scale)
    chip_pad_y = int(5 * scale)

    # Let the circle size scale nicely with temp height
    circle_d = int(temp_h + 16 * scale)
    icon_w = circle_d

    line1_width = icon_w + icon_gap + temp_w
    line1_height = circle_d
    chip_width = location_w + chip_pad_x * 2
    chip_height = location_h + chip_pad_y * 2

    card_width = max(chip_width, line1_width, condition_w, meta_w) + card_padding * 2
    card_width = min(card_width, int(width * 0.78))
    card_height = chip_height + outer_gap + line1_height + row_gap + condition_h + row_gap + meta_h + card_padding * 2

    margin = int(24 * scale)
    if layout_position == "bottom_left":
        x = margin
        y = height - margin - card_height
    elif layout_position == "bottom_right":
        x = width - margin - card_width
        y = height - margin - card_height
    elif layout_position == "top_left":
        x = margin
        y = margin
    else:
        x = width - margin - card_width
        y = margin

    card_radius = int(30 * scale)

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Start compositing
    result_img = img.copy()

    # 1. Shadow layer (soft, premium blurred shadow)
    shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    shadow_draw.rounded_rectangle(
        [
            x + int(4 * scale),
            y + int(6 * scale),
            x + card_width + int(4 * scale),
            y + card_height + int(6 * scale)
        ],
        radius=card_radius,
        fill=(0, 0, 0, 110)
    )
    shadow_blurred = shadow_layer.filter(ImageFilter.GaussianBlur(radius=max(12, int(20 * scale))))
    result_img = Image.alpha_composite(result_img, shadow_blurred)

    # 2. Glassmorphic blurred card background (True Frosted Glass)
    crop_box = (int(x), int(y), int(x + card_width), int(y + card_height))
    # Ensure crop stays within image boundaries
    crop_x1 = max(0, min(width - 1, crop_box[0]))
    crop_y1 = max(0, min(height - 1, crop_box[1]))
    crop_x2 = max(0, min(width, crop_box[2]))
    crop_y2 = max(0, min(height, crop_box[3]))

    card_bg = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    card_blur = card_bg.filter(ImageFilter.GaussianBlur(radius=max(18, int(26 * scale))))

    # Mask for rounded corners
    mask = Image.new("L", (card_width, card_height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, card_width, card_height], radius=card_radius, fill=255)

    # Draw vertical sky gradient over the blurred card background
    gradient_img = Image.new("RGBA", (card_width, card_height))
    grad_draw = ImageDraw.Draw(gradient_img)
    top_c, bot_c, _ = _weather_gradient(weather_info["weather_code"])
    for y_offset in range(card_height):
        ratio = y_offset / max(1, card_height - 1)
        r = int(top_c[0] * (1 - ratio) + bot_c[0] * ratio)
        g = int(top_c[1] * (1 - ratio) + bot_c[1] * ratio)
        b = int(top_c[2] * (1 - ratio) + bot_c[2] * ratio)
        grad_draw.line([(0, y_offset), (card_width, y_offset)], fill=(r, g, b, 190))

    card_combined = Image.alpha_composite(card_blur.convert("RGBA"), gradient_img)
    result_img.paste(card_combined, (int(x), int(y)), mask=mask)

    # 3. Drawing overlay (colored tints, borders, texts, icons)
    overlay_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_layer)

    card_box = [x, y, x + card_width, y + card_height]

    # Glass highlight overlay (very subtle overlay on top of gradient)
    draw.rounded_rectangle(card_box, radius=card_radius, fill=(255, 255, 255, 15))

    # Clean glass outline
    draw.rounded_rectangle(
        card_box,
        radius=card_radius,
        outline=(255, 255, 255, 60),
        width=1,
    )

    # Location Chip
    chip_box = [
        x + card_padding,
        y + card_padding,
        x + card_padding + chip_width,
        y + card_padding + chip_height,
    ]
    draw.rounded_rectangle(
        chip_box,
        radius=max(6, chip_height // 2),
        fill=(255, 255, 255, 20),
        outline=(255, 255, 255, 50),
        width=1,
    )
    draw.text(
        (chip_box[0] + chip_pad_x, chip_box[1] + chip_pad_y),
        location_text,
        font=font_location,
        fill=(255, 255, 255, 220),
    )

    curr_y = chip_box[3] + outer_gap

    # Weather row circle accent
    circle_box = [
        x + card_padding,
        curr_y,
        x + card_padding + circle_d,
        curr_y + circle_d,
    ]
    draw.ellipse(circle_box, fill=accent_rgb + (35,))
    draw.ellipse(circle_box, outline=(255, 255, 255, 45), width=1)

    # Draw beautiful vector weather icon centered in the circle accent
    icon_cx = circle_box[0] + circle_d / 2
    icon_cy = circle_box[1] + circle_d / 2
    _draw_weather_icon(draw, icon_cx, icon_cy, circle_d * 0.65, weather_info["weather_code"], scale)

    # Draw temperature
    temp_x = circle_box[2] + icon_gap
    temp_y = curr_y + max(0, (circle_d - temp_h) // 2) - int(3 * scale)
    draw.text((temp_x, temp_y), temp_str, font=font_temp, fill=(255, 255, 255, 250))

    # Weather condition description (e.g. "CLOUDY")
    desc_y = circle_box[3] + row_gap
    draw.text((x + card_padding, desc_y), condition_text, font=font_desc, fill=(255, 255, 255, 240))

    # Date metadata
    meta_y = desc_y + condition_h + row_gap
    draw.text((x + card_padding, meta_y), date_text, font=font_meta, fill=(255, 255, 255, 170))

    combined = Image.alpha_composite(result_img, overlay_layer)
    return combined.convert("RGB")



