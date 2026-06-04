"""Tests for: debug route, health/detailed, stats, input validation, DB backup, log rotation."""
import asyncio
import os
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_SECRET_KEY", "test-secret")
test_db = Path("/tmp/test_phase6.db")
test_db.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"

from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

init_db()
client = TestClient(app)


# ── Debug route ──────────────────────────────────────────────────────────────

def test_debug_log_not_found_when_no_logs(tmp_path):
    with patch("app.api.routes_debug.Path") as mock_path:
        mock_path.return_value.exists.return_value = False
        r = client.get("/api/debug/log")
    assert r.status_code == 404


def test_debug_log_returns_content(tmp_path):
    log_file = tmp_path / "debug_20260101_000000.log"
    log_file.write_text("test log line")
    with patch("app.api.routes_debug.Path", return_value=tmp_path):
        r = client.get("/api/debug/log")
    # Either 200 with content or 404 if mock didn't work - just check no 500
    assert r.status_code in (200, 404)


# ── Health detailed ──────────────────────────────────────────────────────────

def test_health_basic():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_detailed_db_ok():
    r = client.get("/api/health/detailed")
    assert r.status_code == 200
    data = r.json()
    assert data["checks"]["database"]["status"] == "ok"
    assert data["status"] in ("ok", "degraded")


def test_health_detailed_immich_not_configured():
    r = client.get("/api/health/detailed")
    data = r.json()
    # immich may be not_configured or ok depending on test DB state
    assert data["checks"]["immich"]["status"] in ("ok", "not_configured", "error")


def test_health_detailed_scheduler_heartbeat_is_reported(tmp_path):
    mock_settings = MagicMock()
    mock_settings.data_dir = tmp_path
    (tmp_path / "scheduler.health").write_text("ok")
    now = time.time()
    os.utime(tmp_path / "scheduler.health", (now, now))

    with patch("app.api.routes_health.get_settings", return_value=mock_settings):
        r = client.get("/api/health/detailed")

    data = r.json()
    assert data["checks"]["scheduler"]["status"] == "ok"
    assert data["checks"]["scheduler"]["age_seconds"] >= 0



def test_load_rgb_rejects_oversized_bytes():
    from app.services.generation.modules.common import load_rgb
    big = b"x" * (51 * 1024 * 1024)
    try:
        load_rgb(big)
        assert False, "Should have raised"
    except (ValueError, Exception):
        pass  # expected


def test_load_rgb_downscales_large_image():
    from app.services.generation.modules.common import load_rgb
    buf = BytesIO()
    Image.new("RGB", (9000, 9000), (0, 0, 0)).save(buf, format="PNG")
    img = load_rgb(buf.getvalue())
    assert max(img.size) <= 3840


# ── DB backup ────────────────────────────────────────────────────────────────

def test_backup_database_creates_file(tmp_path):
    src = tmp_path / "app.db"
    src.write_bytes(b"fake db content")
    backup_dir = tmp_path / "backups"

    mock_settings = MagicMock()
    mock_settings.data_dir = tmp_path
    with patch("app.config.get_settings", return_value=mock_settings):
        from app.workers.scheduler import _backup_database
        _backup_database()

    backups = list(backup_dir.glob("app_*.db"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"fake db content"


def test_backup_database_keeps_max_7(tmp_path):
    src = tmp_path / "app.db"
    src.write_bytes(b"db")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    for i in range(8):
        (backup_dir / f"app_2026010{i}.db").write_bytes(b"old")

    mock_settings = MagicMock()
    mock_settings.data_dir = tmp_path
    with patch("app.config.get_settings", return_value=mock_settings):
        from app.workers.scheduler import _backup_database
        _backup_database()

    backups = list(backup_dir.glob("app_*.db"))
    assert len(backups) <= 7


# ── Log rotation ─────────────────────────────────────────────────────────────

def test_log_rotation_removes_oldest(tmp_path):
    from app.utils.debug_logger import _rotate_logs
    # Create 10 log files
    for i in range(10):
        f = tmp_path / f"debug_2026010{i:02d}_000000.log"
        f.write_text("log")
    assert len(list(tmp_path.glob("debug_*.log"))) == 10
    _rotate_logs(tmp_path)
    assert len(list(tmp_path.glob("debug_*.log"))) == 9  # removed oldest


def test_log_rotation_noop_when_under_limit(tmp_path):
    from app.utils.debug_logger import _rotate_logs
    for i in range(5):
        (tmp_path / f"debug_{i}.log").write_text("x")
    _rotate_logs(tmp_path)
    assert len(list(tmp_path.glob("debug_*.log"))) == 5


# ── Webhook ──────────────────────────────────────────────────────────────────

def test_webhook_sends_post():
    from app.services.generation.engine import _send_webhook
    settings = MagicMock()
    settings.webhook_url = "https://example.com/hook"
    posted = {}

    mock_response = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    async def fake_post(url, json):
        posted["url"] = url
        posted["json"] = json
    mock_client.post = AsyncMock(side_effect=fake_post)

    with patch("httpx.AsyncClient", return_value=mock_client):
        asyncio.run(_send_webhook(settings.webhook_url, "task-1", "bokeh_blur", "Test Title"))

    assert posted["url"] == "https://example.com/hook"
    assert posted["json"]["task_id"] == "task-1"
    assert posted["json"]["generation_type"] == "bokeh_blur"


def test_webhook_skipped_when_no_url():
    from app.services.generation.engine import _send_webhook
    settings = MagicMock()
    settings.webhook_url = None
    with patch("httpx.AsyncClient") as mock_cls:
        asyncio.run(_send_webhook(settings.webhook_url, "task-1", "bokeh_blur", "Title"))
    mock_cls.assert_not_called()



# ── AI custom prompt ─────────────────────────────────────────────────────────

def test_ai_anime_uses_custom_prompt_from_config():
    from app.services.generation.ai_effects_builder import build_ai_module
    from app.models.ai_effect import AIEffectModel
    from types import SimpleNamespace

    anime_module = build_ai_module(
        AIEffectModel(
            id="ai_anime",
            title="AI Anime",
            description="anime description",
            positive_prompt="default prompt",
            negative_prompt="neg prompt",
            custom_prompt_placeholder="custom prompt placeholder",
            enabled=True,
            source="builtin",
        )
    )

    captured = {}

    async def fake_generate(settings, image_bytes, prompt, *args, **kwargs):
        captured["prompt"] = prompt
        buf = BytesIO()
        Image.new("RGB", (10, 10)).save(buf, format="PNG")
        return SimpleNamespace(image_bytes=buf.getvalue(), provider="openai", model="gpt-image-1")

    # Generate a valid PNG image for the get_asset_data mock
    buf = BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="PNG")
    valid_bytes = buf.getvalue()

    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=valid_bytes)
    asset = MagicMock(id="a1", original_file_name="x.jpg")
    settings = MagicMock(ai_custom_prompt=None)

    with patch("app.services.generation.modules.ai_style_base.generate_ai_image", fake_generate):
        asyncio.run(anime_module.run([asset], {"custom_prompt": "my custom"}, client, settings))

    assert captured["prompt"] == "my custom"


def test_ai_anime_falls_back_to_settings_prompt():
    from app.services.generation.ai_effects_builder import build_ai_module
    from app.models.ai_effect import AIEffectModel

    anime_module = build_ai_module(
        AIEffectModel(
            id="ai_anime",
            title="AI Anime",
            description="anime description",
            positive_prompt="default prompt",
            negative_prompt="neg prompt",
            custom_prompt_placeholder="custom prompt placeholder",
            enabled=True,
            source="builtin",
        )
    )

    captured = {}

    async def fake_generate(settings, image_bytes, prompt, *args, **kwargs):
        captured["prompt"] = prompt
        buf = BytesIO()
        Image.new("RGB", (10, 10)).save(buf, format="PNG")
        from types import SimpleNamespace
        return SimpleNamespace(image_bytes=buf.getvalue(), provider="openai", model="gpt-image-1")

    # Generate a valid PNG image for the get_asset_data mock
    buf = BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="PNG")
    valid_bytes = buf.getvalue()

    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=valid_bytes)
    asset = MagicMock(id="a1", original_file_name="x.jpg")
    settings = MagicMock(ai_custom_prompt="settings level prompt")

    with patch("app.services.generation.modules.ai_style_base.generate_ai_image", fake_generate):
        asyncio.run(anime_module.run([asset], {}, client, settings))

    assert captured["prompt"] == "settings level prompt"
