import asyncio
from io import BytesIO

from PIL import Image

from app.models.settings import SettingsModel
from app.services.generation.modules.apple_weather import AppleWeatherModule


class MockImmichClient:
    def __init__(self, exif_data, asset_info_data=None):
        self.exif_data = exif_data
        self.asset_info_data = asset_info_data or {}

    async def get_asset_data(self, asset_id):
        img = Image.new("RGB", (120, 120), "white")
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


def test_apple_weather_module_run_weather_mode(monkeypatch):
    async def mock_fetch_weather(lat, lon, dt):
        return {"temp_c": 22.5, "weather_code": 3}

    async def mock_reverse_geocode(lat, lon):
        return "Piaseczno"

    from app.services.generation.modules import apple_weather

    monkeypatch.setattr(apple_weather, "fetch_weather", mock_fetch_weather)
    monkeypatch.setattr(apple_weather, "reverse_geocode", mock_reverse_geocode)

    module = AppleWeatherModule()
    client = MockImmichClient(
        exif_data={
            "latitude": 52.0725,
            "longitude": 21.02,
            "dateTimeOriginal": "2025-06-04T12:34:56Z",
        }
    )
    settings = SettingsModel()

    class DummyAsset:
        id = "asset-apple-weather"
        created_at = "2025-06-04T12:34:56Z"
        original_file_name = "weather.jpg"

    res = asyncio.run(module.run([DummyAsset()], {"units": "celsius"}, client, settings))

    assert res.generation_type == "apple_weather"
    assert res.config["mode"] == "apple_weather"
    assert "Piaseczno" in res.summary
    assert "22°C" in res.summary
    assert len(res.image_bytes) > 0
