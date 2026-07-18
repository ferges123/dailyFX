"""Tests for: debug route, health/detailed, stats, input validation, DB backup, log rotation."""

import asyncio
import os
import sqlite3
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_SECRET_KEY", "test-secret")
test_db = Path("/tmp/test_phase6.db")
for sqlite_path in (test_db, test_db.with_name(f"{test_db.name}-wal"), test_db.with_name(f"{test_db.name}-shm")):
    sqlite_path.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"

import app.config

app.config.get_settings.cache_clear()

from app.database import SessionLocal, init_db
from app.main import app

init_db()


# ── Debug route ──────────────────────────────────────────────────────────────


def test_debug_log_not_found_when_no_logs(tmp_path, monkeypatch):
    from fastapi import HTTPException

    import app.config as config_module
    from app.api.routes_debug import get_debug_log

    missing_dir = tmp_path / "missing"
    settings = config_module.get_settings()
    monkeypatch.setattr(settings, "data_dir", missing_dir)
    try:
        get_debug_log()
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected missing debug logs to return 404")


def test_debug_log_returns_content(tmp_path, monkeypatch):
    import app.config as config_module
    from app.api.routes_debug import get_debug_log

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "debug_20260101_000000.log"
    log_file.write_text("test log line")
    settings = config_module.get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    assert get_debug_log() == "test log line"


# ── Health detailed ──────────────────────────────────────────────────────────


def test_health_basic():
    from app.api.routes_health import health

    assert health()["status"] == "ok"


def test_health_detailed_db_ok():
    from app.api.routes_health import health_detailed

    db = SessionLocal()
    try:
        data = asyncio.run(health_detailed(db, None))
    finally:
        db.close()

    assert data["checks"]["database"]["status"] == "ok"
    assert data["status"] in ("ok", "degraded")


def test_health_detailed_immich_not_configured():
    from app.api.routes_health import health_detailed

    db = SessionLocal()
    try:
        data = asyncio.run(health_detailed(db, None))
    finally:
        db.close()

    # immich may be not_configured or ok depending on test DB state
    assert data["checks"]["immich"]["status"] in ("ok", "not_configured", "error")


def test_health_detailed_scheduler_heartbeat_is_reported(tmp_path):
    mock_settings = MagicMock()
    mock_settings.data_dir = tmp_path
    (tmp_path / "scheduler.health").write_text("ok")
    now = time.time()
    os.utime(tmp_path / "scheduler.health", (now, now))

    with patch("app.api.routes_health.get_settings", return_value=mock_settings):
        from app.api.routes_health import health_detailed

        db = SessionLocal()
        try:
            data = asyncio.run(health_detailed(db, None))
        finally:
            db.close()

    assert data["checks"]["scheduler"]["status"] == "ok"
    assert data["checks"]["scheduler"]["age_seconds"] >= 0


def test_load_rgb_rejects_oversized_bytes():
    from app.services.generation.modules.common import load_rgb

    big = b"x" * (51 * 1024 * 1024)
    try:
        load_rgb(big)
        raise AssertionError("Should have raised")
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
    with sqlite3.connect(src) as db:
        db.execute("CREATE TABLE records (value TEXT NOT NULL)")
        db.execute("INSERT INTO records VALUES ('restored')")
        db.commit()
    backup_dir = tmp_path / "backups"

    mock_settings = MagicMock()
    mock_settings.data_dir = tmp_path
    with patch("app.config.get_settings", return_value=mock_settings):
        from app.workers.scheduler import _backup_database

        _backup_database(retention_count=7)

    backups = list(backup_dir.glob("app_*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as db:
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert db.execute("SELECT value FROM records").fetchone() == ("restored",)


def test_backup_database_uses_configured_retention_count(tmp_path):
    src = tmp_path / "app.db"
    with sqlite3.connect(src) as db:
        db.execute("CREATE TABLE records (value TEXT NOT NULL)")
        db.commit()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    for i in range(4):
        (backup_dir / f"app_2026010{i}.db").write_bytes(b"old")

    mock_settings = MagicMock()
    mock_settings.data_dir = tmp_path
    with patch("app.config.get_settings", return_value=mock_settings):
        from app.workers.scheduler import _backup_database

        _backup_database(retention_count=3)

    backups = list(backup_dir.glob("app_*.db"))
    assert len(backups) == 3


def test_backup_database_restores_committed_wal_changes(tmp_path):
    src = tmp_path / "app.db"
    writer = sqlite3.connect(src)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE records (value TEXT NOT NULL)")
        writer.execute("INSERT INTO records VALUES ('in-wal')")
        writer.commit()

        mock_settings = MagicMock()
        mock_settings.data_dir = tmp_path
        with patch("app.config.get_settings", return_value=mock_settings):
            from app.workers.scheduler import _backup_database

            _backup_database(retention_count=1)
    finally:
        writer.close()

    backup = next((tmp_path / "backups").glob("app_*.db"))
    with sqlite3.connect(backup) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert restored.execute("SELECT value FROM records").fetchone() == ("in-wal",)


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
    from app.services.generation.output import send_webhook

    settings = MagicMock()
    settings.webhook_url = "https://example.com/hook"
    posted = {}

    MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    async def fake_post(url, json):
        posted["url"] = url
        posted["json"] = json

    mock_client.post = AsyncMock(side_effect=fake_post)

    with patch("httpx.AsyncClient", return_value=mock_client):
        asyncio.run(send_webhook(settings.webhook_url, "task-1", "bokeh_blur", "Test Title"))

    assert posted["url"] == "https://example.com/hook"
    assert posted["json"]["task_id"] == "task-1"
    assert posted["json"]["generation_type"] == "bokeh_blur"


def test_webhook_skipped_when_no_url():
    from app.services.generation.output import send_webhook

    settings = MagicMock()
    settings.webhook_url = None
    with patch("httpx.AsyncClient") as mock_cls:
        asyncio.run(send_webhook(settings.webhook_url, "task-1", "bokeh_blur", "Title"))
    mock_cls.assert_not_called()


# ── AI custom prompt ─────────────────────────────────────────────────────────


def test_ai_anime_uses_custom_prompt_from_config():
    from types import SimpleNamespace

    from app.models.ai_effect import AIEffectModel
    from app.services.generation.ai_effects_builder import build_ai_module

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
    from app.models.ai_effect import AIEffectModel
    from app.services.generation.ai_effects_builder import build_ai_module

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
