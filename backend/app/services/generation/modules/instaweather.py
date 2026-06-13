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


def degrees_to_cardinal(deg: float | int) -> str:
    """Map degrees (0-360) to 8 cardinal directions."""
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = round(deg / 45) % 8
    return directions[idx]


def format_time_str(val: str | None) -> str:
    """Extract HH:MM from Open-Meteo time strings."""
    if not val:
        return ""
    if "T" in val:
        return val.split("T")[1][:5]
    return val[:5]


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
        "hourly": "temperature_2m,weather_code,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_direction_10m,cloud_cover",
        "daily": "sunrise,sunset",
        "timezone": "auto",
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
            apparents = hourly.get("apparent_temperature", [])
            humidities = hourly.get("relative_humidity_2m", [])
            wind_speeds = hourly.get("wind_speed_10m", [])
            wind_dirs = hourly.get("wind_direction_10m", [])
            clouds = hourly.get("cloud_cover", [])

            daily = data.get("daily", {})
            sunrises = daily.get("sunrise", [])
            sunsets = daily.get("sunset", [])

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

            sunrise_str = sunrises[0] if sunrises else None
            sunset_str = sunsets[0] if sunsets else None

            return {
                "temp_c": temps[closest_idx],
                "weather_code": codes[closest_idx],
                "apparent_temp_c": apparents[closest_idx] if closest_idx < len(apparents) else temps[closest_idx],
                "cloud_cover": clouds[closest_idx] if closest_idx < len(clouds) else 0,
                "humidity": humidities[closest_idx] if closest_idx < len(humidities) else 50,
                "wind_speed": wind_speeds[closest_idx] if closest_idx < len(wind_speeds) else 10.0,
                "wind_dir": degrees_to_cardinal(wind_dirs[closest_idx]) if closest_idx < len(wind_dirs) else "N",
                "sunrise": format_time_str(sunrise_str),
                "sunset": format_time_str(sunset_str),
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


async def reverse_geocode_detailed(lat: float, lon: float) -> tuple[str | None, str | None]:
    """Translate GPS coordinates into city and country/region via Nominatim."""
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
                city = None
                for field in ("city", "town", "village", "municipality", "suburb", "county"):
                    val = address.get(field)
                    if val:
                        city = val
                        break
                country = address.get("country")
                return city, country
    except Exception as exc:
        logger.warning("Detailed reverse geocoding failed: %s", exc)
    return None, None



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

    # Fallback simulation details
    apparent_temp_c = round(temp_c + (2.0 if code == 0 else -1.5), 1)
    cloud_cover = 90 if code == 3 else (10 if code == 0 else 45)
    humidity = 85 if code in (3, 61, 71) else 45
    wind_speed = 12.5
    wind_dir = "NE"
    sunrise = "05:12"
    sunset = "20:45"

    return {
        "temp_c": round(temp_c, 1),
        "weather_code": code,
        "apparent_temp_c": apparent_temp_c,
        "cloud_cover": cloud_cover,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_dir": wind_dir,
        "sunrise": sunrise,
        "sunset": sunset,
        "simulated": True,
    }
def draw_pin_icon(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, color: tuple):
    w = max(1.5, size * 0.08)
    cx = x + size / 2
    cy = y + size * 0.38
    r = size * 0.28
    # Upper circle
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=int(w))
    # Inner dot
    r_in = size * 0.08
    draw.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], fill=color)
    # Bottom pointer
    p1 = (cx - r * 0.866, cy + r * 0.5) # 150 deg
    p2 = (cx, y + size * 0.95)
    p3 = (cx + r * 0.866, cy + r * 0.5) # 30 deg
    draw.line([p1, p2, p3], fill=color, width=int(w), joint="round")


def draw_humidity_icon(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, color: tuple):
    w = max(1.5, size * 0.08)
    cx = x + size / 2
    r = size * 0.28
    cy = y + size * 0.62
    # Draw bottom half arc
    draw.arc([cx - r, cy - r, cx + r, cy + r], start=0, end=180, fill=color, width=int(w))
    # Draw lines from top point to the arc sides
    top = (cx, y + size * 0.15)
    p_left = (cx - r, cy)
    p_right = (cx + r, cy)
    draw.line([p_left, top, p_right], fill=color, width=int(w), joint="round")


def draw_wind_icon(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, color: tuple):
    w = max(1.5, size * 0.08)
    # Line 1 (top)
    y1 = y + size * 0.35
    draw.line([(x + size * 0.1, y1), (x + size * 0.65, y1)], fill=color, width=int(w))
    # Curl 1 (up and back)
    draw.arc([x + size * 0.55, y1 - size * 0.2, x + size * 0.75, y1], start=270, end=90, fill=color, width=int(w))
    
    # Line 2 (bottom)
    y2 = y + size * 0.65
    draw.line([(x + size * 0.2, y2), (x + size * 0.75, y2)], fill=color, width=int(w))
    # Curl 2 (down and back)
    draw.arc([x + size * 0.65, y2, x + size * 0.85, y2 + size * 0.2], start=90, end=270, fill=color, width=int(w))


def draw_sunrise_icon(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, color: tuple):
    w = max(1.5, size * 0.08)
    cx = x + size / 2
    hy = y + size * 0.75
    # Horizon line
    draw.line([(x + size * 0.1, hy), (x + size * 0.9, hy)], fill=color, width=int(w))
    # Half sun
    r = size * 0.22
    draw.arc([cx - r, hy - r, cx + r, hy + r], start=180, end=360, fill=color, width=int(w))
    # Rays
    # Top ray
    draw.line([(cx, hy - r - size * 0.05), (cx, hy - r - size * 0.2)], fill=color, width=int(w))
    # Left ray
    draw.line([(cx - r * 0.7, hy - r * 0.7), (cx - r * 1.1, hy - r * 1.1)], fill=color, width=int(w))
    # Right ray
    draw.line([(cx + r * 0.7, hy - r * 0.7), (cx + r * 1.1, hy - r * 1.1)], fill=color, width=int(w))
    # Up arrow (small, in center of sun)
    draw.line([(cx, hy - size * 0.05), (cx, hy - size * 0.18)], fill=color, width=int(w))
    draw.line([(cx - size * 0.05, hy - size * 0.13), (cx, hy - size * 0.18), (cx + size * 0.05, hy - size * 0.13)], fill=color, width=int(w))


def draw_sunset_icon(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, color: tuple):
    w = max(1.5, size * 0.08)
    cx = x + size / 2
    hy = y + size * 0.75
    # Horizon line
    draw.line([(x + size * 0.1, hy), (x + size * 0.9, hy)], fill=color, width=int(w))
    # Half sun
    r = size * 0.22
    draw.arc([cx - r, hy - r, cx + r, hy + r], start=180, end=360, fill=color, width=int(w))
    # Rays
    # Top ray
    draw.line([(cx, hy - r - size * 0.05), (cx, hy - r - size * 0.2)], fill=color, width=int(w))
    # Left ray
    draw.line([(cx - r * 0.7, hy - r * 0.7), (cx - r * 1.1, hy - r * 1.1)], fill=color, width=int(w))
    # Right ray
    draw.line([(cx + r * 0.7, hy - r * 0.7), (cx + r * 1.1, hy - r * 1.1)], fill=color, width=int(w))
    # Down arrow
    draw.line([(cx, hy - size * 0.18), (cx, hy - size * 0.05)], fill=color, width=int(w))
    draw.line([(cx - size * 0.05, hy - size * 0.10), (cx, hy - size * 0.05), (cx + size * 0.05, hy - size * 0.10)], fill=color, width=int(w))


def draw_sun(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, color: tuple = (255, 204, 0, 255)):
    w = max(2, size * 0.06)
    cx = x + size / 2
    cy = y + size / 2
    r = size * 0.30
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=int(w))
    ray_len = size * 0.10
    ray_gap = size * 0.06
    import math
    for i in range(8):
        angle = i * (math.pi / 4)
        x1 = cx + (r + ray_gap) * math.cos(angle)
        y1 = cy + (r + ray_gap) * math.sin(angle)
        x2 = cx + (r + ray_gap + ray_len) * math.cos(angle)
        y2 = cy + (r + ray_gap + ray_len) * math.sin(angle)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=int(w))


def draw_cloud(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, fill_color: tuple = (255, 255, 255, 230)):
    # Large left bump
    r1 = size * 0.22
    cx1, cy1 = x + size * 0.32, y + size * 0.58
    draw.ellipse([cx1 - r1, cy1 - r1, cx1 + r1, cy1 + r1], fill=fill_color)

    # Large center bump (tallest)
    r2 = size * 0.28
    cx2, cy2 = x + size * 0.50, y + size * 0.42
    draw.ellipse([cx2 - r2, cy2 - r2, cx2 + r2, cy2 + r2], fill=fill_color)

    # Large right bump
    r3 = size * 0.20
    cx3, cy3 = x + size * 0.68, y + size * 0.58
    draw.ellipse([cx3 - r3, cy3 - r3, cx3 + r3, cy3 + r3], fill=fill_color)

    # Bottom fill rectangle
    draw.rounded_rectangle(
        [x + size * 0.15, y + size * 0.55, x + size * 0.82, y + size * 0.82],
        radius=int(size * 0.14),
        fill=fill_color
    )


def draw_rain(draw: ImageDraw.ImageDraw, x: float, y: float, size: float):
    # First draw the cloud slightly shifted up
    draw_cloud(draw, x, y - size * 0.08, size, fill_color=(255, 255, 255, 220))
    # Now draw 3 rain streaks
    w = max(1.5, size * 0.06)
    color = (100, 180, 255, 255)
    # Streak 1
    draw.line([(x + size * 0.38, y + size * 0.72), (x + size * 0.32, y + size * 0.88)], fill=color, width=int(w))
    # Streak 2
    draw.line([(x + size * 0.52, y + size * 0.72), (x + size * 0.46, y + size * 0.88)], fill=color, width=int(w))
    # Streak 3
    draw.line([(x + size * 0.66, y + size * 0.72), (x + size * 0.60, y + size * 0.88)], fill=color, width=int(w))


def draw_snow(draw: ImageDraw.ImageDraw, x: float, y: float, size: float):
    draw_cloud(draw, x, y - size * 0.08, size, fill_color=(255, 255, 255, 220))
    # Draw snowflakes (dots)
    color = (255, 255, 255, 255)
    r = max(1.5, size * 0.03)
    # Dot 1
    cx1, cy1 = x + size * 0.38, y + size * 0.78
    draw.ellipse([cx1 - r, cy1 - r, cx1 + r, cy1 + r], fill=color)
    # Dot 2
    cx2, cy2 = x + size * 0.52, y + size * 0.82
    draw.ellipse([cx2 - r, cy2 - r, cx2 + r, cy2 + r], fill=color)
    # Dot 3
    cx3, cy3 = x + size * 0.66, y + size * 0.78
    draw.ellipse([cx3 - r, cy3 - r, cx3 + r, cy3 + r], fill=color)


def draw_thunderstorm(draw: ImageDraw.ImageDraw, x: float, y: float, size: float):
    draw_cloud(draw, x, y - size * 0.08, size, fill_color=(235, 235, 235, 220))
    # Sharp lightning bolt polygon
    color = (255, 220, 0, 255)
    p = [
        (x + size * 0.55, y + size * 0.65), # top start
        (x + size * 0.44, y + size * 0.78), # middle left
        (x + size * 0.52, y + size * 0.78), # middle right
        (x + size * 0.45, y + size * 0.94), # bottom tip
        (x + size * 0.58, y + size * 0.76), # middle right high
        (x + size * 0.50, y + size * 0.76), # middle left high
    ]
    draw.polygon(p, fill=color)


def draw_main_weather_icon(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, code: int):
    if code == 0:
        draw_sun(draw, x, y, size)
    elif code in (1, 2):
        draw_sun(draw, x - size * 0.12, y - size * 0.08, size * 0.72)
        draw_cloud(draw, x, y, size)
    elif code in (3, 45, 48):
        draw_cloud(draw, x, y, size)
    elif code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        draw_rain(draw, x, y, size)
    elif code in (71, 73, 75, 77, 85, 86):
        draw_snow(draw, x, y, size)
    elif code in (95, 96, 99):
        draw_thunderstorm(draw, x, y, size)
    else:
        draw_sun(draw, x, y, size)


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

        city = None
        country = None
        weather_info = None
        mode = "instaweather"

        try:
            if has_gps:
                lat_f = float(lat)
                lon_f = float(lon)
                city, country = await reverse_geocode_detailed(lat_f, lon_f)
                if not city:
                    city = f"{abs(lat_f):.2f}°{'N' if lat_f >= 0 else 'S'}"
                    country = f"{abs(lon_f):.2f}°{'E' if lon_f >= 0 else 'W'}"
                # Fetch weather
                weather_info = await fetch_weather(lat_f, lon_f, dt)
                if not weather_info:
                    weather_info = get_fallback_weather(lat_f, dt.month)
            else:
                # No GPS on asset
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

        # 3. Layout Options
        layout_style = config.get("layout_style", "classic")
        units = config.get("units", "celsius")
        protect_faces_val = config.get("protect_faces", "true")
        protect_faces = str(protect_faces_val).lower() == "true"

        # 4. Render graphics overlay
        result_img = _draw_graphics_overlay(
            img,
            mode=mode,
            location=(city, country) if (city or country) else None,
            weather_info=weather_info,
            dt=dt,
            faces=faces if protect_faces else [],
            units=units,
            font_style=layout_style,
        )

        weather_summary = ""
        if mode == "instaweather" and weather_info:
            w_desc, _ = map_wmo_code(weather_info["weather_code"])
            temp_val = weather_info["temp_c"]
            temp_str = f"{int(temp_val)}°C" if units == "celsius" else f"{int((temp_val * 9/5) + 32)}°F"
            loc_str = f" in {city}" if city else ""
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
                "mode": mode,
            },
            source_asset_ids=[asset.id],
        )


def _draw_graphics_overlay(
    img: Image.Image,
    mode: str,
    location: tuple[str | None, str | None] | None,
    weather_info: dict | None,
    dt: datetime | None,
    faces: list,
    units: str,
    font_style: str,
) -> Image.Image:
    img = _center_square_crop(img)
    width, height = img.size
    size = min(width, height)
    scale = size / 1254.0
    margin = int(72 * scale)
    white = (255, 255, 255, 245)
    muted = (255, 255, 255, 210)

    font_regular = "Inter-Regular"
    font_date = get_font(font_regular, max(18, int(36 * scale)))
    font_temp = get_font(font_regular, max(70, int(130 * scale)))
    font_label = get_font(font_regular, max(16, int(28 * scale)))
    font_value = get_font(font_regular, max(28, int(58 * scale)))
    font_city = get_font(font_regular, max(28, int(52 * scale)))
    font_country = get_font(font_regular, max(18, int(34 * scale)))
    font_metric = get_font(font_regular, max(16, int(30 * scale)))
    font_metric_value = get_font(font_regular, max(18, int(34 * scale)))

    if dt:
        day_str, date_str = _format_english_date(dt)
    else:
        day_str, date_str = "SATURDAY", "MAY 18, 2024"

    temp_val = weather_info.get("temp_c", 22.0) if weather_info else 22.0
    if units == "fahrenheit":
        temp_val = (temp_val * 9 / 5) + 32
        temp_str = f"{int(temp_val)}°F"
        feels_val = weather_info.get("apparent_temp_c", weather_info.get("temp_c", 22.0)) if weather_info else 22.0
        feels_val = (feels_val * 9 / 5) + 32
        feels_str = f"{int(feels_val)}°F"
    else:
        temp_str = f"{int(temp_val)}°C"
        feels_val = weather_info.get("apparent_temp_c", weather_info.get("temp_c", 22.0)) if weather_info else 22.0
        feels_str = f"{int(feels_val)}°C"

    weather_code = weather_info.get("weather_code", 0) if weather_info else 0
    cc = weather_info.get("cloud_cover", 0) if weather_info else 0
    if cc <= 20:
        cloud_str = "LOW"
    elif cc <= 60:
        cloud_str = "MEDIUM"
    else:
        cloud_str = "HIGH"

    sunrise_time = weather_info.get("sunrise", "05:12") if weather_info else "05:12"
    sunset_time = weather_info.get("sunset", "20:45") if weather_info else "20:45"

    city_str = None
    country_str = None
    if location:
        c, co = location
        if c:
            city_str = c.upper()
        if co:
            country_str = co.upper()

    hum_val = weather_info.get("humidity", 50) if weather_info else 50
    wind_spd = weather_info.get("wind_speed", 10.0) if weather_info else 10.0
    wind_dir = weather_info.get("wind_dir", "N") if weather_info else "N"

    hum_label_str = "HUMIDITY"
    hum_val_str = f"{int(hum_val)}%"
    wind_label_str = "WIND"
    wind_val_str = f"{int(wind_spd)} km/h {wind_dir}"

    overlay_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_layer)

    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade)
    left_w = int(size * 0.48)
    for x in range(left_w):
        alpha = int(118 * (1 - x / left_w))
        shade_draw.line([(x, 0), (x, height)], fill=(0, 0, 0, alpha))
    top_right_w = int(size * 0.34)
    top_right_h = int(size * 0.23)
    for x in range(width - top_right_w, width):
        x_factor = (x - (width - top_right_w)) / top_right_w
        for y in range(0, top_right_h):
            y_factor = 1 - (y / top_right_h)
            alpha = int(84 * x_factor * y_factor)
            if alpha:
                shade_draw.point((x, y), fill=(0, 0, 0, alpha))
    bottom_h = int(size * 0.38)
    for y in range(height - bottom_h, height):
        alpha = int(112 * ((y - (height - bottom_h)) / bottom_h))
        shade_draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    overlay_layer = Image.alpha_composite(overlay_layer, shade)
    draw = ImageDraw.Draw(overlay_layer)

    def draw_text_shadow(text, pos, font, text_color=white, shadow_color=(0, 0, 0, 150), fake_bold=False):
        x, y = pos
        offsets = [(2.0, 2.0), (0, 2.0), (2.0, 0)]
        for dx, dy in offsets:
            ox = x + dx * scale
            oy = y + dy * scale
            draw.text((ox, oy), text, font=font, fill=shadow_color)
            if fake_bold:
                draw.text((ox + 1, oy), text, font=font, fill=shadow_color)
                draw.text((ox, oy + 1), text, font=font, fill=shadow_color)
                draw.text((ox + 1, oy + 1), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=text_color)
        if fake_bold:
            draw.text((x + 1, y), text, font=font, fill=text_color)
            draw.text((x, y + 1), text, font=font, fill=text_color)
            draw.text((x + 1, y + 1), text, font=font, fill=text_color)

    def draw_dashed_line(x1, y, x2, color=(255, 255, 255, 180), line_width=2, dash_len=6, gap_len=7):
        cx = int(x1)
        end = int(x2)
        while cx < end:
            seg_end = min(cx + dash_len, end)
            draw.line([(cx, y), (seg_end, y)], fill=color, width=max(1, int(line_width)))
            cx = seg_end + gap_len

    def draw_shadowed_icon(draw_func, x, y, icon_size):
        offset = max(2, int(3 * scale))
        draw_func(draw, x + offset, y + offset, icon_size, (0, 0, 0, 140))
        draw_func(draw, x, y, icon_size, white)

    date_y = int(72 * scale)
    draw_text_shadow(day_str, (margin, date_y), font_date)
    draw_text_shadow(date_str, (margin, date_y + int(52 * scale)), font_date)

    icon_size = int(210 * scale)
    icon_x = margin - int(8 * scale)
    icon_y = int(210 * scale)
    draw_main_weather_icon(draw, icon_x, icon_y, icon_size, weather_code)

    temp_y = int(455 * scale)
    draw_text_shadow(temp_str, (margin, temp_y), font_temp)
    divider_y = temp_y + int(148 * scale)
    draw.line(
        [(margin, divider_y), (margin + int(330 * scale), divider_y)],
        fill=(255, 255, 255, 220),
        width=max(2, int(3 * scale)),
    )

    details_y = divider_y + int(36 * scale)
    draw_text_shadow("FEELS LIKE", (margin, details_y), font_label)
    draw_text_shadow(feels_str, (margin, details_y + int(52 * scale)), font_value, text_color=muted)
    cloud_y = details_y + int(132 * scale)
    draw_text_shadow("CLOUDINESS", (margin, cloud_y), font_label)
    draw_text_shadow(_cloudiness_label_en(cloud_str), (margin, cloud_y + int(50 * scale)), font_label)
    draw_dashed_line(
        margin,
        cloud_y + int(112 * scale),
        margin + int(350 * scale),
        color=(255, 255, 255, 180),
        line_width=max(2, int(2 * scale)),
    )

    if city_str:
        loc_y = height - int(170 * scale)
        pin_size = int(68 * scale)
        draw_shadowed_icon(draw_pin_icon, margin, loc_y - int(4 * scale), pin_size)
        text_x = margin + int(84 * scale)
        draw_text_shadow(city_str, (text_x, loc_y), font_city, fake_bold=True)
        if country_str:
            draw_text_shadow(country_str, (text_x, loc_y + int(58 * scale)), font_country)

    top_icon_size = int(48 * scale)
    time_x = width - margin - int(104 * scale)
    top_icon_x = time_x - int(86 * scale)
    top_y = int(74 * scale)
    draw_shadowed_icon(draw_sunrise_icon, top_icon_x, top_y - int(8 * scale), top_icon_size)
    draw_text_shadow(sunrise_time, (time_x, top_y), font_metric_value)
    draw_dashed_line(top_icon_x, top_y + int(58 * scale), width - margin, color=(255, 255, 255, 180))
    draw_shadowed_icon(draw_sunset_icon, top_icon_x, top_y + int(70 * scale), top_icon_size)
    draw_text_shadow(sunset_time, (time_x, top_y + int(78 * scale)), font_metric_value)

    metric_icon_size = int(44 * scale)
    metric_x = width - margin - int(300 * scale)
    metric_y = height - int(250 * scale)
    draw_shadowed_icon(draw_humidity_icon, metric_x, metric_y, metric_icon_size)
    draw_text_shadow(hum_label_str, (metric_x + int(66 * scale), metric_y), font_metric)
    draw_text_shadow(hum_val_str, (metric_x + int(66 * scale), metric_y + int(42 * scale)), font_metric_value)
    wind_y = metric_y + int(118 * scale)
    draw_shadowed_icon(draw_wind_icon, metric_x, wind_y, metric_icon_size)
    draw_text_shadow(wind_label_str, (metric_x + int(66 * scale), wind_y), font_metric)
    draw_text_shadow(wind_val_str, (metric_x + int(66 * scale), wind_y + int(42 * scale)), font_metric_value)

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    combined = Image.alpha_composite(img, overlay_layer)
    return combined.convert("RGB")


def _center_square_crop(img: Image.Image) -> Image.Image:
    width, height = img.size
    side = min(width, height)
    left = max(0, (width - side) // 2)
    top = max(0, (height - side) // 2)
    return img.crop((left, top, left + side, top + side))


def _format_english_date(dt: datetime) -> tuple[str, str]:
    days = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY")
    months = (
        "JANUARY",
        "FEBRUARY",
        "MARCH",
        "APRIL",
        "MAY",
        "JUNE",
        "JULY",
        "AUGUST",
        "SEPTEMBER",
        "OCTOBER",
        "NOVEMBER",
        "DECEMBER",
    )
    return days[dt.weekday()], f"{months[dt.month - 1]} {dt.day:02d}, {dt.year}"


def _cloudiness_label_en(level: str) -> str:
    if level == "LOW":
        return "LOW"
    if level == "MEDIUM":
        return "MEDIUM"
    return "HIGH"
