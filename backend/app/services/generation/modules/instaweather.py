from __future__ import annotations

import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import httpx

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import get_font, save_png, load_rgb

logger = logging.getLogger(__name__)


def map_wmo_code(code: int) -> tuple[str, str]:
    """Map WMO weather code to description and emoji."""
    if code == 0:
        return "Clear sky", "☀️"
    elif code in (1, 2):
        return "Partly cloudy", "⛅"
    elif code == 3:
        return "Cloudy", "☁️"
    elif code in (45, 48):
        return "Foggy", "🌫️"
    elif code in (51, 53, 55):
        return "Drizzle", "🌧️"
    elif code in (56, 57):
        return "Freezing drizzle", "🌧️"
    elif code in (61, 63, 65):
        return "Rain", "🌧️"
    elif code in (66, 67):
        return "Freezing rain", "🌧️"
    elif code in (71, 73, 75, 77):
        return "Snowfall", "❄️"
    elif code in (80, 81, 82):
        return "Rain showers", "🌧️"
    elif code in (85, 86):
        return "Snow showers", "❄️"
    elif code in (95, 96, 99):
        return "Thunderstorm", "⛈️"
    return "Clear", "☀️"


def calculate_season_and_icon(month: int) -> tuple[str, str]:
    """Calculate season and corresponding icon from month number."""
    if month in (3, 4, 5):
        return "Spring", "🌸"
    elif month in (6, 7, 8):
        return "Summer", "☀️"
    elif month in (9, 10, 11):
        return "Autumn", "🍁"
    else:
        return "Winter", "❄️"


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


async def fetch_weather(lat: float, lon: float, dt: datetime) -> dict | None:
    """Fetch weather status from Open-Meteo Forecast or Archive API."""
    date_str = dt.strftime("%Y-%m-%d")
    hour = dt.hour
    now = datetime.utcnow()
    is_recent = (now - dt).days <= 2

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

        has_gps = (lat not in (None, "")) and (lon not in (None, ""))

        location = None
        weather_info = None
        mode = "instatime"

        if has_gps and dt:
            try:
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
                mode = "instaweather"
            except Exception as e:
                logger.warning("Metadata fetch failed for InstaWeather: %s", e)

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
            # We estimate card dimensions for collision check
            # Default estimated size
            card_width_est = int(320 * scale)
            card_height_est = int(120 * scale)

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

    # Draw card inset and thin white border frame
    margin_inset = int(15 * scale)
    
    # Fonts loading with larger sizes
    font_name = "Inter-Regular" if font_style == "classic" else "PlayfairDisplay-Medium"
    title_size = max(24, int(30 * scale))
    subtitle_size = max(16, int(20 * scale))
    meta_size = max(12, int(15 * scale))

    font_title = get_font(font_name, title_size)
    font_sub = get_font("Inter-Regular", subtitle_size)
    font_meta = get_font("Inter-Regular", meta_size)

    # Resolve labels - Headline is weather details (with icon & temp)
    if mode == "instaweather" and weather_info:
        temp_val = weather_info["temp_c"]
        if units == "fahrenheit":
            temp_val = (temp_val * 9 / 5) + 32
            temp_str = f"{int(temp_val)}°F"
        else:
            temp_str = f"{int(temp_val)}°C"

        w_desc, w_emoji = map_wmo_code(weather_info["weather_code"])
        line1 = f"{w_emoji} {temp_str} • {w_desc}"
        line2 = location or "Nearby"
    else:
        month = dt.month if dt else 6
        season, season_icon = calculate_season_and_icon(month)
        line1 = f"{season_icon} {season.upper()}"
        line2 = dt.strftime("%B %d, %Y").upper() if dt else "UNKNOWN DATE"

    line3 = dt.strftime("%A • %H:%M") if dt else ""

    # Measure text height and widths to establish box bounds
    temp_img = Image.new("RGBA", (100, 100))
    temp_draw = ImageDraw.Draw(temp_img)

    w1, h1 = get_text_size(line1, font_title, temp_draw)
    w2, h2 = get_text_size(line2, font_sub, temp_draw)
    w3, h3 = get_text_size(line3, font_meta, temp_draw) if line3 else (0, 0)

    card_padding = int(16 * scale)
    line_spacing = int(6 * scale)

    card_width = max(w1, w2, w3) + card_padding * 2
    card_width = min(card_width, int(width * 0.65))  # Limit to 65% width

    card_height = h1 + h2 + (h3 + line_spacing if line3 else 0) + line_spacing + card_padding * 2

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

    # Drawing layer
    overlay_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_layer)

    # Inset border card outline
    draw.rectangle(
        [margin_inset, margin_inset, width - margin_inset, height - margin_inset],
        outline=(255, 255, 255, 240),
        width=max(1, int(2.5 * scale))
    )

    card_box = [x, y, x + card_width, y + card_height]
    card_radius = int(12 * scale)

    # Dark translucent container
    draw.rounded_rectangle(card_box, radius=card_radius, fill=(24, 24, 27, 150))
    # Border outline for card itself
    draw.rounded_rectangle(card_box, radius=card_radius, outline=(255, 255, 255, 45), width=1)

    curr_y = y + card_padding

    draw.text((x + card_padding, curr_y), line1, font=font_title, fill=(255, 255, 255, 255))
    curr_y += h1 + line_spacing

    draw.text((x + card_padding, curr_y), line2, font=font_sub, fill=(228, 228, 231, 230))
    curr_y += h2 + line_spacing

    if line3:
        draw.text((x + card_padding, curr_y), line3, font=font_meta, fill=(161, 161, 170, 200))

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    combined = Image.alpha_composite(img, overlay_layer)
    return combined.convert("RGB")
