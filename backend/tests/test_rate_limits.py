import pytest


@pytest.fixture(autouse=True)
def enable_limiter():
    from app.limiter import limiter

    limiter.enabled = True
    yield
    limiter.enabled = False


def test_limiter_module_exists():
    from app.limiter import limiter

    assert limiter is not None


def test_studio_preview_rate_limit():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        # Create a dummy file and data that passes FastAPI's form validation
        files = {"file": ("test.jpg", b"dummy_content", "image/jpeg")}
        data = {"effect_id": "bokeh_blur", "config": "{}"}

        # Send 5 requests (all should bypass or return non-429 since limit is 5/minute)
        for _ in range(5):
            response = client.post("/api/studio/preview", files=files, data=data)
            assert response.status_code != 429

        # 6th request must exceed limit and return 429
        response = client.post("/api/studio/preview", files=files, data=data)
        assert response.status_code == 429


def test_settings_update_rate_limit():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        payload = {
            "immich_url": "https://immich.example.test",
            "immich_api_key": "immich-secret-1234",
            "openai_api_key": "sk-openai-9876",
            "gemini_api_key": "gemini-4567",
            "xiaomi_api_key": "mimo-secret-2468",
            "ai_vision_hourly_limit": 25,
            "ai_image_hourly_limit": 7,
        }

        # Limit is 10/minute
        for _ in range(10):
            response = client.put("/api/settings", json=payload)
            assert response.status_code != 429

        # 11th request must exceed limit and return 429
        response = client.put("/api/settings", json=payload)
        assert response.status_code == 429


def test_schedule_run_now_rate_limit():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        # Limit is 10/minute
        for _ in range(10):
            response = client.post("/api/schedules/9999/run-now")
            assert response.status_code != 429

        # 11th request must exceed limit and return 429
        response = client.post("/api/schedules/9999/run-now")
        assert response.status_code == 429
