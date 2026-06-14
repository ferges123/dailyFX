from fastapi.testclient import TestClient

import app.config as config_module
from app.main import app


def test_debug_log_endpoint_no_auth(tmp_path, monkeypatch):
    # Ensure APP_ACCESS_TOKEN is not set
    monkeypatch.delenv("APP_ACCESS_TOKEN", raising=False)
    config_module.get_settings.cache_clear()

    # Create dummy log file
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "debug_2026-06-12.log"
    log_file.write_text("test log content")

    # Patch data_dir in settings
    settings = config_module.get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    with TestClient(app) as client:
        response = client.get("/api/debug/log")
        assert response.status_code == 200
        assert response.text == "test log content"


def test_debug_log_endpoint_with_auth(tmp_path, monkeypatch):
    # Enforce APP_ACCESS_TOKEN
    monkeypatch.setenv("APP_ACCESS_TOKEN", "super-secret-debug-token")
    config_module.get_settings.cache_clear()

    # Create dummy log file
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "debug_2026-06-12.log"
    log_file.write_text("test log content")

    # Patch data_dir in settings
    settings = config_module.get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    with TestClient(app) as client:
        # 1. Try unauthenticated
        response = client.get("/api/debug/log")
        assert response.status_code == 401

        # 2. Try with wrong token
        response = client.get("/api/debug/log", headers={"Authorization": "Bearer bad-token"})
        assert response.status_code == 401

        # 3. Try with correct token
        response = client.get("/api/debug/log", headers={"Authorization": "Bearer super-secret-debug-token"})
        assert response.status_code == 200
        assert response.text == "test log content"

    # Reset setting
    monkeypatch.delenv("APP_ACCESS_TOKEN", raising=False)
    config_module.get_settings.cache_clear()
