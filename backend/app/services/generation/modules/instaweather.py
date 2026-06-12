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
    w = max(1.5, size * 0.08)
    cx = x + size / 2
    cy = y + size / 2
    r = size * 0.22
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=int(w))
    # 8 rays
    ray_len = size * 0.12
    ray_gap = size * 0.08
    import math
    for i in range(8):
        angle = i * (math.pi / 4)
        x1 = cx + (r + ray_gap) * math.cos(angle)
        y1 = cy + (r + ray_gap) * math.sin(angle)
        x2 = cx + (r + ray_gap + ray_len) * math.cos(angle)
        y2 = cy + (r + ray_gap + ray_len) * math.sin(angle)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=int(w))


def draw_cloud(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, fill_color: tuple = (255, 255, 255, 230)):
    # Left circle
    r1 = size * 0.18
    cx1, cy1 = x + size * 0.35, y + size * 0.6
    draw.ellipse([cx1 - r1, cy1 - r1, cx1 + r1, cy1 + r1], fill=fill_color)
    
    # Middle circle
    r2 = size * 0.23
    cx2, cy2 = x + size * 0.52, y + size * 0.45
    draw.ellipse([cx2 - r2, cy2 - r2, cx2 + r2, cy2 + r2], fill=fill_color)
    
    # Right circle
    r3 = size * 0.15
    cx3, cy3 = x + size * 0.68, y + size * 0.62
    draw.ellipse([cx3 - r3, cy3 - r3, cx3 + r3, cy3 + r3], fill=fill_color)
    
    # Bottom rect
    draw.rounded_rectangle(
        [x + size * 0.25, y + size * 0.55, x + size * 0.75, y + size * 0.78],
        radius=int(size * 0.12),
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
    width, height = img.size
    min_dim = min(width, height)
    scale = min_dim / 1000.0

    margin = int(0.07 * min_dim)
    # Proportional font sizes
    fs_date = max(14, int(18 * scale))
    fs_temp = max(56, int(82 * scale))
    fs_label = max(12, int(15 * scale))
    fs_metric = max(14, int(20 * scale))
    fs_city = max(18, int(26 * scale))

    # Font names
    font_name = "Inter-Regular"
    font_date = get_font(font_name, fs_date)
    font_temp = get_font(font_name, fs_temp)
    font_label = get_font(font_name, fs_label)
    font_metric = get_font(font_name, fs_metric)
    font_city = get_font(font_name, fs_city)

    # Temporary drawing surface for size measuring
    temp_img = Image.new("RGBA", (100, 100))
    temp_draw = ImageDraw.Draw(temp_img)

    # 1. Day & Date Block (Top-Left)
    if dt:
        day_str = dt.strftime("%A").upper()
        date_str = dt.strftime("%B %d, %Y").upper()
    else:
        day_str = "SATURDAY"
        date_str = "MAY 18, 2024"

    w_day, h_day = get_text_size(day_str, font_date, temp_draw)
    w_date, h_date = get_text_size(date_str, font_date, temp_draw)
    w_tl = max(w_day, w_date)
    h_tl = h_day + int(8 * scale) + h_date

    # 2. Main Weather Block (Left-Middle)
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

    icon_sz = int(130 * scale)
    w_temp, h_temp = get_text_size(temp_str, font_temp, temp_draw)
    div_len = int(0.3 * width)

    h_label_feels = get_text_height("FEELS LIKE", font_label, temp_draw)
    h_val_feels = get_text_height(feels_str, font_date, temp_draw)
    h_label_cloud = get_text_height("CLOUDINESS", font_label, temp_draw)
    h_val_cloud = get_text_height(cloud_str, font_date, temp_draw)

    gap_y = int(8 * scale)
    h_lm = (icon_sz + gap_y +
            h_temp + gap_y +
            int(4 * scale) +
            gap_y +
            h_label_feels + int(2 * scale) + h_val_feels + gap_y +
            h_label_cloud + int(2 * scale) + h_val_cloud +
            gap_y + int(2 * scale))
    w_lm = max(icon_sz, w_temp, div_len)

    # 3. Sunrise & Sunset Block (Top-Right)
    sunrise_time = weather_info.get("sunrise", "05:12") if weather_info else "05:12"
    sunset_time = weather_info.get("sunset", "20:45") if weather_info else "20:45"
    
    icon_sz_sec = int(28 * scale)
    w_sr_t, h_sr_t = get_text_size(sunrise_time, font_metric, temp_draw)
    w_ss_t, h_ss_t = get_text_size(sunset_time, font_metric, temp_draw)
    
    row_height = max(icon_sz_sec, h_sr_t, h_ss_t)
    w_tr = icon_sz_sec + int(10 * scale) + max(w_sr_t, w_ss_t)
    h_tr = row_height * 2 + gap_y

    # 4. Location Block (Bottom-Left)
    city_str = None
    country_str = None
    if location:
        c, co = location
        if c:
            city_str = c.upper()
        if co:
            country_str = co.upper()

    w_bl = 0
    h_bl = 0
    if city_str:
        w_city, h_city = get_text_size(city_str, font_city, temp_draw)
        w_country, h_country = get_text_size(country_str or "", font_date, temp_draw)
        w_bl = icon_sz_sec + int(10 * scale) + max(w_city, w_country)
        h_bl = max(icon_sz_sec, h_city) + (gap_y + h_country if country_str else 0)

    # 5. Humidity & Wind Block (Bottom-Right)
    hum_val = weather_info.get("humidity", 50) if weather_info else 50
    wind_spd = weather_info.get("wind_speed", 10.0) if weather_info else 10.0
    wind_dir = weather_info.get("wind_dir", "N") if weather_info else "N"
    
    hum_label_str = "HUMIDITY"
    hum_val_str = f"{int(hum_val)}%"
    wind_label_str = "WIND"
    wind_val_str = f"{int(wind_spd)} KM/H {wind_dir}"
    
    w_hum_label, h_hum_label = get_text_size(hum_label_str, font_label, temp_draw)
    w_hum_val, h_hum_val = get_text_size(hum_val_str, font_date, temp_draw)
    w_wind_label, h_wind_label = get_text_size(wind_label_str, font_label, temp_draw)
    w_wind_val, h_wind_val = get_text_size(wind_val_str, font_date, temp_draw)
    w_br = icon_sz_sec + int(10 * scale) + max(w_hum_label, w_hum_val, w_wind_label, w_wind_val)
    h_br = (row_height + int(2 * scale) + h_hum_val + gap_y +
            row_height + int(2 * scale) + h_wind_val)

    # Helper function to check collision with faces
    def check_collision(box):
        bx1, by1, bx2, by2 = box
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
                if bx1 < fx2 and bx2 > fx1 and by1 < fy2 and by2 > fy1:
                    return True
        return False

    # Calculate shifting & visibility
    # Top-Left Block
    tl_x = margin
    tl_y = margin
    tl_hidden = False
    if faces:
        shifted = False
        for sx in range(0, int(150 * scale), int(25 * scale)):
            if not check_collision([tl_x + sx, tl_y, tl_x + sx + w_tl, tl_y + h_tl]):
                tl_x += sx
                shifted = True
                break
        if not shifted:
            for sy in range(0, int(150 * scale), int(25 * scale)):
                if not check_collision([tl_x, tl_y + sy, tl_x + w_tl, tl_y + sy + h_tl]):
                    tl_y += sy
                    shifted = True
                    break
        if not shifted:
            tl_hidden = True

    # Top-Right Block
    tr_x = width - margin - w_tr
    tr_y = margin
    tr_hidden = False
    if faces:
        shifted = False
        for sx in range(0, int(150 * scale), int(25 * scale)):
            if not check_collision([tr_x - sx, tr_y, tr_x - sx + w_tr, tr_y + h_tr]):
                tr_x -= sx
                shifted = True
                break
        if not shifted:
            for sy in range(0, int(150 * scale), int(25 * scale)):
                if not check_collision([tr_x, tr_y + sy, tr_x + w_tr, tr_y + sy + h_tr]):
                    tr_y += sy
                    shifted = True
                    break
        if not shifted:
            tr_hidden = True

    # Bottom-Left Block
    bl_x = margin
    bl_y = height - margin - h_bl
    bl_hidden = not city_str
    if faces and not bl_hidden:
        shifted = False
        for sx in range(0, int(150 * scale), int(25 * scale)):
            if not check_collision([bl_x + sx, bl_y, bl_x + sx + w_bl, bl_y + h_bl]):
                bl_x += sx
                shifted = True
                break
        if not shifted:
            for sy in range(0, int(150 * scale), int(25 * scale)):
                if not check_collision([bl_x, bl_y - sy, bl_x + w_bl, bl_y - sy + h_bl]):
                    bl_y -= sy
                    shifted = True
                    break
        if not shifted:
            bl_hidden = True

    # Bottom-Right Block
    br_x = width - margin - w_br
    br_y = height - margin - h_br
    br_hidden = False
    if faces:
        shifted = False
        for sx in range(0, int(150 * scale), int(25 * scale)):
            if not check_collision([br_x - sx, br_y, br_x - sx + w_br, br_y + h_br]):
                br_x -= sx
                shifted = True
                break
        if not shifted:
            for sy in range(0, int(150 * scale), int(25 * scale)):
                if not check_collision([br_x, br_y - sy, br_x + w_br, br_y - sy + h_br]):
                    br_y -= sy
                    shifted = True
                    break
        if not shifted:
            br_hidden = True

    # Left-Middle Block (Swaps sides if left is blocked, shifts vertically otherwise)
    lm_x = margin
    lm_y = (height - h_lm) // 2
    lm_hidden = False
    if faces:
        shifted = False
        for sy in [0, int(-50 * scale), int(50 * scale), int(-100 * scale), int(100 * scale), int(-150 * scale), int(150 * scale)]:
            test_y = lm_y + sy
            if test_y >= margin and test_y + h_lm <= height - margin:
                if not check_collision([lm_x, test_y, lm_x + w_lm, test_y + h_lm]):
                    lm_y = test_y
                    shifted = True
                    break
        if not shifted:
            # Swap to right side
            lm_x = width - margin - w_lm
            for sy in [0, int(-50 * scale), int(50 * scale), int(-100 * scale), int(100 * scale), int(-150 * scale), int(150 * scale)]:
                test_y = lm_y + sy
                if test_y >= margin and test_y + h_lm <= height - margin:
                    if not check_collision([lm_x, test_y, lm_x + w_lm, test_y + h_lm]):
                        lm_y = test_y
                        shifted = True
                        break
        if not shifted:
            lm_hidden = True

    # Drawing layer
    overlay_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_layer)

    # Helper function to draw text with drop shadow
    def draw_text_shadow(text, pos, font, text_color=(255, 255, 255, 245), shadow_color=(0, 0, 0, 140), fake_bold=False):
        x, y = pos
        offsets = [(-1.5, -1.5), (-1.5, 1.5), (1.5, -1.5), (1.5, 1.5), (0, 1.5), (0, -1.5), (1.5, 0), (-1.5, 0)]
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

    def draw_dashed_line(x1, y, x2, color=(255, 255, 255, 160), line_width=2, dash_len=10, gap_len=8):
        cx = int(x1)
        end = int(x2)
        while cx < end:
            seg_end = min(cx + dash_len, end)
            draw.line([(cx, y), (seg_end, y)], fill=color, width=max(1, int(line_width)))
            cx = seg_end + gap_len

    # Render Top-Left (Day/Date)
    if not tl_hidden:
        draw_text_shadow(day_str, (tl_x, tl_y), font_date)
        draw_text_shadow(date_str, (tl_x, tl_y + h_day + int(8 * scale)), font_date)

    # Render Top-Right (Sunrise/Sunset)
    if not tr_hidden:
        time_x = tr_x + icon_sz_sec + int(10 * scale)

        # Row 1: Sunrise with icon
        sr_icon_y = tr_y + (row_height - icon_sz_sec) // 2
        draw_sunrise_icon(draw, tr_x, sr_icon_y, icon_sz_sec, (255, 255, 255, 245))
        sr_text_y = tr_y + (row_height - h_sr_t) // 2
        draw_text_shadow(sunrise_time, (time_x, sr_text_y), font_metric)

        # Dashed Divider between sunrise and sunset
        div_y = tr_y + row_height + gap_y // 2
        draw_dashed_line(tr_x, div_y, tr_x + w_tr, color=(255, 255, 255, 140), line_width=max(1, int(1.5 * scale)))

        # Row 2: Sunset with icon
        ss_icon_y = tr_y + row_height + gap_y + (row_height - icon_sz_sec) // 2
        draw_sunset_icon(draw, tr_x, ss_icon_y, icon_sz_sec, (255, 255, 255, 245))
        ss_text_y = tr_y + row_height + gap_y + (row_height - h_ss_t) // 2
        draw_text_shadow(sunset_time, (time_x, ss_text_y), font_metric)

    # Render Bottom-Left (Location)
    if not bl_hidden and city_str:
        pin_y = bl_y + (max(icon_sz_sec, h_city) - icon_sz_sec) // 2
        draw_pin_icon(draw, bl_x, pin_y, icon_sz_sec, (255, 255, 255, 245))

        city_x = bl_x + icon_sz_sec + int(10 * scale)
        city_y = bl_y + (max(icon_sz_sec, h_city) - h_city) // 2
        draw_text_shadow(city_str, (city_x, city_y), font_city, fake_bold=True)

        if country_str:
            country_y = bl_y + max(icon_sz_sec, h_city) + gap_y
            draw_text_shadow(country_str, (city_x, country_y), font_date)

    # Render Bottom-Right (Metrics) - label on top, value below
    if not br_hidden:
        metric_x = br_x + icon_sz_sec + int(10 * scale)

        # Humidity: icon + label on top, value below
        hum_icon_y = br_y + (row_height - icon_sz_sec) // 2
        draw_humidity_icon(draw, br_x, hum_icon_y, icon_sz_sec, (255, 255, 255, 245))
        hum_label_y = br_y + (row_height - h_hum_label) // 2
        draw_text_shadow(hum_label_str, (metric_x, hum_label_y), font_label, text_color=(255, 255, 255, 200))
        hum_val_y = br_y + row_height + int(2 * scale)
        draw_text_shadow(hum_val_str, (metric_x, hum_val_y), font_date)

        # Wind: icon + label on top, value below
        wind_block_y = br_y + row_height + int(2 * scale) + h_hum_val + gap_y
        wind_icon_y = wind_block_y + (row_height - icon_sz_sec) // 2
        draw_wind_icon(draw, br_x, wind_icon_y, icon_sz_sec, (255, 255, 255, 245))
        wind_label_y = wind_block_y + (row_height - h_wind_label) // 2
        draw_text_shadow(wind_label_str, (metric_x, wind_label_y), font_label, text_color=(255, 255, 255, 200))
        wind_val_y = wind_block_y + row_height + int(2 * scale)
        draw_text_shadow(wind_val_str, (metric_x, wind_val_y), font_date)

    # Render Left-Middle (Main Weather detail) - icon first, then temp, divider, secondary
    if not lm_hidden:
        curr_y = lm_y

        # Main weather icon (large, left-aligned)
        draw_main_weather_icon(draw, lm_x, curr_y, icon_sz, weather_code)
        curr_y += icon_sz + gap_y

        # Temperature (large, left-aligned)
        draw_text_shadow(temp_str, (lm_x, curr_y), font_temp)
        curr_y += h_temp + gap_y

        # Solid divider line (like reference)
        draw.line([(lm_x, curr_y), (lm_x + div_len, curr_y)], fill=(255, 255, 255, 200), width=max(1, int(2 * scale)))
        curr_y += gap_y + int(4 * scale)

        # Feels Like block (left-aligned)
        feels_lbl_w, feels_lbl_h = get_text_size("FEELS LIKE", font_label, temp_draw)
        draw_text_shadow("FEELS LIKE", (lm_x, curr_y), font_label, text_color=(255, 255, 255, 180))
        curr_y += feels_lbl_h + int(2 * scale)
        draw_text_shadow(feels_str, (lm_x, curr_y), font_date)
        curr_y += get_text_height(feels_str, font_date, temp_draw) + gap_y

        # Cloudiness block (left-aligned)
        draw_text_shadow("CLOUDINESS", (lm_x, curr_y), font_label, text_color=(255, 255, 255, 180))
        curr_y += get_text_height("CLOUDINESS", font_label, temp_draw) + int(2 * scale)
        draw_text_shadow(cloud_str, (lm_x, curr_y), font_date)
        curr_y += get_text_height(cloud_str, font_date, temp_draw) + gap_y

        # Dashed separator line after cloudiness (full width of left block)
        draw_dashed_line(lm_x, curr_y, lm_x + div_len, color=(255, 255, 255, 140), line_width=max(1, int(1.5 * scale)))

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    combined = Image.alpha_composite(img, overlay_layer)
    return combined.convert("RGB")

