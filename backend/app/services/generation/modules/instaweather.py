from __future__ import annotations

import logging
from datetime import UTC, datetime
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import httpx

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import get_font, save_png, load_rgb

logger = logging.getLogger(__name__)


def map_wmo_code(code: int) -> tuple[str, str]:
    """Map WMO weather code to description and emoji."""
    if code == 0:
        return "Clear sky", "☀"
    elif code in (1, 2):
        return "Partly cloudy", "☁"
    elif code == 3:
        return "Cloudy", "☁"
    elif code in (45, 48):
        return "Foggy", "☁"
    elif code in (51, 53, 55):
        return "Drizzle", "☔"
    elif code in (56, 57):
        return "Freezing drizzle", "❄"
    elif code in (61, 63, 65):
        return "Rain", "☔"
    elif code in (66, 67):
        return "Freezing rain", "☔"
    elif code in (71, 73, 75, 77):
        return "Snowfall", "❄"
    elif code in (80, 81, 82):
        return "Rain showers", "☔"
    elif code in (85, 86):
        return "Snow showers", "❄"
    elif code in (95, 96, 99):
        return "Thunderstorm", "⚡"
    return "Clear", "☀"


def calculate_season_and_icon(month: int) -> tuple[str, str]:
    """Calculate season and corresponding icon from month number."""
    if month in (3, 4, 5):
        return "Spring", "❀"
    elif month in (6, 7, 8):
        return "Summer", "☀"
    elif month in (9, 10, 11):
        return "Autumn", "❧"
    else:
        return "Winter", "❄"


def parse_date(date_str: str | None) -> datetime | None:
    """Parse ISO or standard EXIF date string into datetime object."""
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    try:
        cleaned = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except ValueError:
        pass
    return None


def get_text_size(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, draw: ImageDraw.ImageDraw) -> tuple[int, int]:
    """Cross-version helper to measure text width and height in PIL."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        return draw.textsize(text, font=font)


def get_text_height(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, draw: ImageDraw.ImageDraw) -> int:
    """Measure the bottom-most pixel offset of the text relative to the top anchor."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[3]
    except AttributeError:
        return draw.textsize(text, font=font)[1]


async def fetch_weather(lat: float, lon: float, dt: datetime) -> dict | None:
    """Fetch weather status from Open-Meteo Forecast or Archive API."""
    date_str = dt.strftime("%Y-%m-%d")
    hour = dt.hour
    now = datetime.now(UTC)
    dt_utc = dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    is_recent = (now - dt_utc).days <= 2

    if is_recent:
        url = "https://api.open-meteo.com/v1/forecast"
    else:
        url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,weather_code",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                # Try the other API as fallback
                fallback_url = (
                    "https://api.open-meteo.com/v1/forecast"
                    if url != "https://api.open-meteo.com/v1/forecast"
                    else "https://archive-api.open-meteo.com/v1/archive"
                )
                response = await client.get(fallback_url, params=params)
                if response.status_code != 200:
                    logger.warning("Open-Meteo weather fetch failed: HTTP %d", response.status_code)
                    return None

            data = response.json()
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            codes = hourly.get("weather_code", [])

            if not temps or not codes:
                return None

            # Locate closest hour index
            closest_idx = 0
            min_diff = 24
            for idx, t_str in enumerate(times):
                try:
                    h = int(t_str.split("T")[1].split(":")[0])
                    diff = abs(h - hour)
                    if diff < min_diff:
                        min_diff = diff
                        closest_idx = idx
                except Exception:
                    pass

            return {
                "temp_c": temps[closest_idx],
                "weather_code": codes[closest_idx],
            }
    except Exception as exc:
        logger.warning("Exception during Open-Meteo weather fetch: %s", exc)
        return None


async def reverse_geocode(lat: float, lon: float) -> str | None:
    """Translate GPS coordinates into a display location string via Nominatim."""
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 10,
    }
    headers = {"User-Agent": "DailyFX/1.0 (dailyfx@localhost)"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                address = data.get("address", {})
                for field in ("city", "town", "village", "municipality", "suburb", "county", "state", "country"):
                    val = address.get(field)
                    if val:
                        return val
    except Exception as exc:
        logger.warning("Reverse geocoding failed: %s", exc)
    return None


def get_fallback_weather(lat: float, month: int) -> dict:
    """Simulate realistic weather conditions based on latitude and month as fallback."""
    abs_lat = abs(lat)
    is_northern = lat >= 0

    if is_northern:
        season_month = month
    else:
        season_month = (month + 6) % 12 or 12

    # Equator is warm year-round (~28C), poles are cold (~-15C base)
    equator_factor = (90 - abs_lat) / 90.0
    base_temp = -15 + 43 * equator_factor

    # Seasonal variation amplitude (larger at higher latitudes)
    amplitude = 15 * (abs_lat / 90.0)

    import math
    seasonal_variation = amplitude * math.sin(math.pi * (season_month - 4) / 6)
    temp_c = base_temp + seasonal_variation

    if temp_c < 0:
        code = 71  # Snow
    elif temp_c < 10:
        code = 3   # Cloudy
    elif seasonal_variation < -5:
        code = 61  # Rain
    else:
        code = 0   # Clear

    return {
        "temp_c": round(temp_c, 1),
        "weather_code": code,
        "simulated": True,
    }


class InstaWeatherModule:
    name = "instaweather"
    label = "InstaWeather"
    description = "Context-aware weather and season watermark overlay with automatic face protection."
    default_weight = 2
    default_config = {
        "layout_style": "classic",
        "units": "celsius",
        "protect_faces": "true",
    }
    config_schema = [
        {
            "key": "layout_style",
            "label": "Layout Style",
            "type": "select",
            "description": "Visual theme of the watermark overlay card.",
            "options": [
                {"value": "classic", "label": "Classic (Inter Sans)"},
                {"value": "postcard", "label": "Postcard (Playfair Serif)"},
            ],
            "default": "classic",
        },
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
            "description": "Auto-shift the watermark overlay to avoid covering detected faces.",
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

        # 1. Gather metadata
        exif_info = await client.get_asset_exif(asset.id)
        lat = exif_info.get("latitude")
        lon = exif_info.get("longitude")
        taken_str = exif_info.get("dateTimeOriginal") or asset.created_at
        dt = parse_date(taken_str)
        if not dt:
            dt = datetime.now()

        has_gps = (lat not in (None, "")) and (lon not in (None, ""))

        location = None
        weather_info = None
        mode = "instaweather"

        try:
            if has_gps:
                lat_f = float(lat)
                lon_f = float(lon)
                # Fetch geocode first
                location = await reverse_geocode(lat_f, lon_f)
                if not location:
                    location = f"{abs(lat_f):.2f}°{'N' if lat_f >= 0 else 'S'}, {abs(lon_f):.2f}°{'E' if lon_f >= 0 else 'W'}"
                # Fetch weather
                weather_info = await fetch_weather(lat_f, lon_f, dt)
                if not weather_info:
                    weather_info = get_fallback_weather(lat_f, dt.month)
            else:
                # No GPS on asset - keep the location blank, but still generate a weather card.
                lat_f = 52.23
                lon_f = 21.01
                weather_info = await fetch_weather(lat_f, lon_f, dt)
                if not weather_info:
                    weather_info = get_fallback_weather(lat_f, dt.month)
        except Exception as e:
            logger.warning("Metadata fetch failed for InstaWeather: %s", e)
            if not weather_info:
                weather_info = get_fallback_weather(52.23, dt.month)

        # 2. Extract faces for collision detection
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
        except Exception as e:
            logger.warning("Failed to load asset faces: %s", e)

        # 3. Determine Layout Position and handle Collision Detection
        layout_style = config.get("layout_style", "classic")
        units = config.get("units", "celsius")
        protect_faces_val = config.get("protect_faces", "true")
        protect_faces = str(protect_faces_val).lower() == "true"

        layout_position = "bottom_left"

        if protect_faces and faces:
            width, height = img.size
            scale = min(width, height) / 1000.0
            margin = int(40 * scale)

            # Build list of candidates
            # Default estimated size
            card_width_est = int(580 * scale)
            card_height_est = int(410 * scale)

            positions_map = {
                "bottom_left": (margin, height - margin - card_height_est, margin + card_width_est, height - margin),
                "bottom_right": (width - margin - card_width_est, height - margin - card_height_est, width - margin, height - margin),
                "top_left": (margin, margin, margin + card_width_est, margin + card_height_est),
                "top_right": (width - margin - card_width_est, margin, width - margin, margin + card_height_est),
            }

            preferred_order = ["bottom_left", "bottom_right", "top_left", "top_right"]
            chosen_position = None

            for pos in preferred_order:
                ox1, oy1, ox2, oy2 = positions_map[pos]
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

                        # Intersection check
                        if fx1 < ox2 and fx2 > ox1 and fy1 < oy2 and fy2 > oy1:
                            collision = True
                            break
                if not collision:
                    chosen_position = pos
                    break

            if chosen_position:
                layout_position = chosen_position
            else:
                layout_position = "bottom_left" # fallback

        # 4. Render graphics overlay
        result_img = _draw_graphics_overlay(
            img,
            mode=mode,
            location=location,
            weather_info=weather_info,
            dt=dt,
            layout_position=layout_position,
            units=units,
            font_style=layout_style,
        )

        weather_summary = ""
        if mode == "instaweather" and weather_info:
            w_desc, _ = map_wmo_code(weather_info["weather_code"])
            temp_val = weather_info["temp_c"]
            temp_str = f"{int(temp_val)}°C" if units == "celsius" else f"{int((temp_val * 9/5) + 32)}°F"
            loc_str = f" in {location}" if location else ""
            weather_summary = f" Weather: {w_desc}, {temp_str}{loc_str}."

        return GenerationResult(
            title=f"InstaWeather: {asset.original_file_name or asset.id}",
            summary=f"Applied context-aware watermark.{weather_summary}",
            image_bytes=save_png(result_img),
            generation_type=self.name,
            provider="local",
            model="pil",
            config={
                "layout_style": layout_style,
                "units": units,
                "protect_faces": protect_faces,
                "resolved_position": layout_position,
                "mode": mode,
            },
            source_asset_ids=[asset.id],
        )


def _draw_graphics_overlay(
    img: Image.Image,
    mode: str,
    location: str | None,
    weather_info: dict | None,
    dt: datetime | None,
    layout_position: str,
    units: str,
    font_style: str,
) -> Image.Image:
    width, height = img.size
    scale = min(width, height) / 1000.0
    is_postcard = font_style == "postcard"

    # Draw a lighter inset frame so the overlay feels like a label, not a panel.
    margin_inset = max(8, int((14 if is_postcard else 13) * scale))

    # Fonts tuned for a cleaner hierarchy.
    font_name = "Inter-Regular" if font_style == "classic" else "PlayfairDisplay-Medium"
    label_size = max(14 if is_postcard else 13, int((18 if is_postcard else 16) * scale))

    icon_size = max(118 if is_postcard else 108, int((164 if is_postcard else 150) * scale))
    temp_size = max(70 if is_postcard else 64, int((100 if is_postcard else 92) * scale))
    desc_size = max(30 if is_postcard else 28, int((38 if is_postcard else 34) * scale))
    loc_size = max(22 if is_postcard else 20, int((27 if is_postcard else 24) * scale))
    meta_size = max(17 if is_postcard else 16, int((20 if is_postcard else 18) * scale))

    # Emojis/weather symbols must be drawn with DejaVuSans to render correctly
    font_label = get_font("Inter-Regular", label_size)
    font_icon = get_font("DejaVuSans", icon_size)
    font_temp = get_font(font_name, temp_size)
    font_desc = get_font("Inter-Regular", desc_size)
    font_loc = get_font("Inter-Regular" if font_style == "classic" else "PlayfairDisplay-Medium", loc_size)
    font_meta = get_font("Inter-Regular", meta_size)

    # Temporary drawing surface for size measuring
    temp_img = Image.new("RGBA", (100, 100))
    temp_draw = ImageDraw.Draw(temp_img)

    # Resolve labels - Headline is weather details (with icon & temp)
    if mode == "instaweather" and weather_info:
        temp_val = weather_info["temp_c"]
        if units == "fahrenheit":
            temp_val = (temp_val * 9 / 5) + 32
            temp_str = f"{int(temp_val)}°F"
        else:
            temp_str = f"{int(temp_val)}°C"

        w_desc, w_emoji = map_wmo_code(weather_info["weather_code"])

        # Horizontal layout: [Icon] [Temp]
        w_icon, _ = get_text_size(w_emoji, font_icon, temp_draw)
        h_icon = get_text_height(w_emoji, font_icon, temp_draw)
        w_temp, _ = get_text_size(temp_str, font_temp, temp_draw)
        h_temp = get_text_height(temp_str, font_temp, temp_draw)

        icon_temp_spacing = int(24 * scale)
        line1_width = w_icon + icon_temp_spacing + w_temp
        line1_height = max(h_icon, h_temp)

        label_text = "FORECAST"
        line2 = w_desc
        footer_time = dt.strftime("%A • %H:%M • %Y") if dt else ""
        footer_location = location or "No location data"
        line3 = f"{footer_location} · {footer_time}" if footer_time else footer_location
    else:
        month = dt.month if dt else 6
        season, season_icon = calculate_season_and_icon(month)

        # Horizontal layout: [Season Icon] [Season Name]
        w_icon, _ = get_text_size(season_icon, font_icon, temp_draw)
        h_icon = get_text_height(season_icon, font_icon, temp_draw)
        season_name = season.upper()
        w_temp, _ = get_text_size(season_name, font_temp, temp_draw)
        h_temp = get_text_height(season_name, font_temp, temp_draw)

        icon_temp_spacing = int(24 * scale)
        line1_width = w_icon + icon_temp_spacing + w_temp
        line1_height = max(h_icon, h_temp)
        label_text = "SEASONAL NOTE"
        line2 = dt.strftime("%B %d, %Y").upper() if dt else "UNKNOWN DATE"
        line3 = dt.strftime("%A • %H:%M") if dt else ""

    label_w, label_h = get_text_size(label_text, font_label, temp_draw)
    w2 = get_text_size(line2, font_desc, temp_draw)[0] if line2 else 0
    h2 = get_text_height(line2, font_desc, temp_draw) if line2 else 0
    w3 = get_text_size(line3, font_loc, temp_draw)[0] if line3 else 0
    h3 = get_text_height(line3, font_loc, temp_draw) if line3 else 0

    card_padding = int((28 if is_postcard else 24) * scale)
    section_gap = int((12 if is_postcard else 10) * scale)
    body_gap = int((10 if is_postcard else 8) * scale)

    card_width = max(label_w + int(24 * scale), line1_width, w2, w3) + card_padding * 2
    card_width = min(card_width, int(width * (0.68 if is_postcard else 0.63)))  # Keep the card compact.

    card_height = label_h + section_gap + line1_height + section_gap + (h2 + body_gap if line2 else 0) + (h3 + body_gap if line3 else 0) + card_padding * 2

    # Placement coordinates nested inside the white inset border
    margin = margin_inset + int(15 * scale)

    if layout_position == "bottom_left":
        x = margin
        y = height - margin - card_height
    elif layout_position == "bottom_right":
        x = width - margin - card_width
        y = height - margin - card_height
    elif layout_position == "top_left":
        x = margin
        y = margin
    elif layout_position == "top_right":
        x = width - margin - card_width
        y = margin
    else:
        x = margin
        y = height - margin - card_height

    # Define colors and options based on style
    if is_postcard:
        # Warm ivory postcard card
        panel_fill = (252, 248, 240, 230)
        panel_outline = (180, 160, 120, 140)
        text_color_main = (30, 35, 45, 245)
        text_color_muted = (30, 35, 45, 180)
        text_color_chip = (30, 35, 45, 200)
        chip_fill = (180, 160, 120, 30)
        chip_outline = (180, 160, 120, 80)
        divider_color = (180, 160, 120, 80)
    else:
        # Completely transparent minimalist classic style
        panel_fill = (0, 0, 0, 0)
        panel_outline = (0, 0, 0, 0)
        text_color_main = (255, 255, 255, 245)
        text_color_muted = (255, 255, 255, 200)
        text_color_chip = (255, 255, 255, 210)
        chip_fill = (255, 255, 255, 20)
        chip_outline = (255, 255, 255, 60)
        divider_color = (255, 255, 255, 60)

    # Drawing layer
    overlay_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_layer)

    card_box = [x, y, x + card_width, y + card_height]
    card_radius = int((18 if is_postcard else 16) * scale)

    # Shadow layer (only for postcard style card)
    if is_postcard:
        shadow_offset = max(6, int((10 if is_postcard else 8) * scale))
        shadow_blur = max(12, int((22 if is_postcard else 18) * scale))
        shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.rounded_rectangle(
            [card_box[0] + shadow_offset, card_box[1] + shadow_offset, card_box[2] + shadow_offset, card_box[3] + shadow_offset],
            radius=card_radius,
            fill=(0, 0, 0, 82),
        )
        overlay_layer = Image.alpha_composite(overlay_layer, shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_blur)))
        draw = ImageDraw.Draw(overlay_layer)

    # Inset border frame (kept subtle and drawn only for Postcard style)
    if is_postcard:
        draw.rectangle(
            [margin_inset, margin_inset, width - margin_inset, height - margin_inset],
            outline=(255, 255, 255, 220),
            width=max(1, int((2.5 if is_postcard else 2.0) * scale))
        )

    # Draw card panel background (if not transparent)
    if panel_fill[3] > 0:
        draw.rounded_rectangle(card_box, radius=card_radius, fill=panel_fill)
        draw.rounded_rectangle(card_box, radius=card_radius, outline=panel_outline, width=1)
        # Highlight top shine
        draw.rounded_rectangle(
            [x + 1, y + 1, x + card_width - 1, y + int(card_height * 0.38)],
            radius=card_radius,
            fill=(255, 255, 255, 12),
        )

        # Subtle elegant gold accent stripe
        accent_x = x + max(2, int(3 * scale))
        draw.rounded_rectangle(
            [accent_x, y + card_padding, accent_x + max(2, int(3 * scale)), y + card_height - card_padding],
            radius=max(1, int(2 * scale)),
            fill=(180, 160, 120, 80),
        )

    curr_y = y + card_padding

    # Helper to draw text with a subtle drop shadow for maximum legibility on transparent backgrounds
    def draw_text_helper(pos, text, font, fill):
        if not is_postcard:
            # Subtle black outline shadow
            draw.text((pos[0] + 1, pos[1] + 1), text, font=font, fill=(0, 0, 0, 140))
        draw.text(pos, text, font=font, fill=fill)

    # Label chip
    label_pad_x = int((12 if is_postcard else 11) * scale)
    label_pad_y = int((7 if is_postcard else 6) * scale)
    label_box = [
        x + card_padding,
        curr_y,
        x + card_padding + label_w + label_pad_x * 2,
        curr_y + label_h + label_pad_y * 2,
    ]
    draw.rounded_rectangle(
        label_box,
        radius=max(10, int(999 * scale)),
        fill=chip_fill,
        outline=chip_outline,
        width=1,
    )
    draw_text_helper(
        (label_box[0] + label_pad_x, label_box[1] + label_pad_y),
        label_text,
        font=font_label,
        fill=text_color_chip,
    )
    curr_y = label_box[3] + section_gap

    # Draw Line 1 (Icon & Temp/Season)
    if mode == "instaweather" and weather_info:
        icon_y = curr_y + max(0, (line1_height - h_icon) // 2)
        temp_y = curr_y + max(0, (line1_height - h_temp) // 2)
        draw_text_helper((x + card_padding, icon_y), w_emoji, font=font_icon, fill=text_color_main)
        draw_text_helper((x + card_padding + w_icon + icon_temp_spacing, temp_y), temp_str, font=font_temp, fill=text_color_main)
    else:
        icon_y = curr_y + max(0, (line1_height - h_icon) // 2)
        temp_y = curr_y + max(0, (line1_height - h_temp) // 2)
        draw_text_helper((x + card_padding, icon_y), season_icon, font=font_icon, fill=text_color_main)
        draw_text_helper((x + card_padding + w_icon + icon_temp_spacing, temp_y), season_name, font=font_temp, fill=text_color_main)

    curr_y += line1_height + section_gap
    divider_y = curr_y - int((section_gap / 2) + 1)
    draw.line(
        [x + card_padding, divider_y, x + card_width - card_padding, divider_y],
        fill=divider_color,
        width=1,
    )

    if line2:
        draw_text_helper((x + card_padding, curr_y), line2, font=font_desc, fill=text_color_main)
        curr_y += h2 + body_gap

    if line3:
        draw_text_helper((x + card_padding, curr_y), line3, font=font_loc, fill=text_color_muted)
        curr_y += h3 + body_gap

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    combined = Image.alpha_composite(img, overlay_layer)
    return combined.convert("RGB")
