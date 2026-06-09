import asyncio
from datetime import datetime
from PIL import Image

from app.models.settings import SettingsModel
from app.services.generation.modules.instaweather import (
    InstaWeatherModule,
    map_wmo_code,
    calculate_season_and_icon,
    parse_date,
)


def test_map_wmo_code():
    assert map_wmo_code(0) == ("Clear sky", "☀")
    assert map_wmo_code(3) == ("Cloudy", "☁")
    assert map_wmo_code(95) == ("Thunderstorm", "⚡")
    assert map_wmo_code(999) == ("Clear", "☀")


def test_calculate_season_and_icon():
    assert calculate_season_and_icon(3) == ("Spring", "❀")
    assert calculate_season_and_icon(6) == ("Summer", "☀")
    assert calculate_season_and_icon(10) == ("Autumn", "❧")
    assert calculate_season_and_icon(12) == ("Winter", "❄")


def test_parse_date():
    assert parse_date("2025-06-04T12:34:56Z") == datetime(2025, 6, 4, 12, 34, 56)
    assert parse_date("2025:06:04 12:34:56") == datetime(2025, 6, 4, 12, 34, 56)
    assert parse_date(None) is None


class MockImmichClient:
    def __init__(self, exif_data, asset_info_data=None):
        self.exif_data = exif_data
        self.asset_info_data = asset_info_data or {}

    async def get_asset_data(self, asset_id):
        img = Image.new("RGB", (100, 100), "white")
        from io import BytesIO
        out = BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    async def get_asset_exif(self, asset_id):
        return self.exif_data

    async def get_asset_info(self, asset_id):
        return self.asset_info_data

    def _coerce_face_summary(self, payload):
        from app.immich.client import ImmichClient
        return ImmichClient._coerce_face_summary(payload)


def test_instaweather_module_run_time_mode():
    module = InstaWeatherModule()
    client = MockImmichClient(exif_data={})
    settings = SettingsModel()

    class DummyAsset:
        id = "asset-1"
        created_at = "2025-06-04T12:34:56Z"
        original_file_name = "test.jpg"

    res = asyncio.run(module.run([DummyAsset()], {}, client, settings))

    assert res.generation_type == "instaweather"
    assert res.config["mode"] == "instaweather"
    assert "Warsaw" not in res.summary
    assert len(res.image_bytes) > 0


def test_instaweather_module_run_weather_mode(monkeypatch):
    async def mock_fetch_weather(lat, lon, dt):
        return {"temp_c": 22.5, "weather_code": 3}

    async def mock_reverse_geocode(lat, lon):
        return "Piaseczno"

    from app.services.generation.modules import instaweather
    monkeypatch.setattr(instaweather, "fetch_weather", mock_fetch_weather)
    monkeypatch.setattr(instaweather, "reverse_geocode", mock_reverse_geocode)

    module = InstaWeatherModule()
    client = MockImmichClient(exif_data={
        "latitude": 52.0725,
        "longitude": 21.02,
        "dateTimeOriginal": "2025-06-04T12:34:56Z",
    })
    settings = SettingsModel()

    class DummyAsset:
        id = "asset-2"
        created_at = "2025-06-04T12:34:56Z"
        original_file_name = "test.jpg"

    res = asyncio.run(module.run([DummyAsset()], {"units": "celsius"}, client, settings))

    assert res.generation_type == "instaweather"
    assert res.config["mode"] == "instaweather"
    assert "Piaseczno" in res.summary
    assert "22°C" in res.summary


def test_fetch_weather_structure():
    # Test that fallback geocode/weather provides all required fields
    from app.services.generation.modules.instaweather import get_fallback_weather
    data = get_fallback_weather(52.23, 6)
    assert "apparent_temp_c" in data
    assert "cloud_cover" in data
    assert "humidity" in data
    assert "wind_speed" in data
    assert "wind_dir" in data
    assert "sunrise" in data
    assert "sunset" in data

