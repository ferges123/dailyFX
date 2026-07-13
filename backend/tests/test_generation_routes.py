import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from _contract_helpers import configure_contract_test_db, make_generation_history_row, make_generation_task_row

from app.api.routes_generation import (
    get_generation_history,
    get_generation_image,
    get_review_page,
    get_task_status,
    list_generation_modules,
)
from app.api.routes_generation_actions import (
    accept_generation,
    reject_generation,
    retry_acceptance,
)
from app.database import SessionLocal
from app.database import init_db as _init_db
from app.models.effect_statistics_log import EffectStatisticsLogModel
from app.models.generation_history import GenerationHistoryModel
from app.models.generation_stream_event import GenerationStreamEventModel
from app.models.generation_task import GenerationTaskModel
from app.services.generation.history import upsert_history_entry
from app.services.generation.stream import get_latest_event_id, replay_gap_requires_resync
from app.services.generation.tasks import update_task
from app.services.immich import get_or_create_settings

test_db = configure_contract_test_db("generation_routes")


def init_db():
    _init_db()


def _make_fake_asset(asset_id="asset-1", filename="photo.jpg"):
    asset = MagicMock()
    asset.id = asset_id
    asset.original_file_name = filename
    asset.created_at = "2024-06-15T10:30:00.000Z"
    return asset


def _make_fake_page(assets):
    page = MagicMock()
    page.items = assets
    return page


def _setup_generation_routes_db():
    init_db()
    db = SessionLocal()
    return db


def _add_history_row(db, task_id: str, output_path: str | None = None, status: str = "PENDING_REVIEW"):
    row = make_generation_history_row(task_id=task_id, output_path=output_path, status=status)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_generation_history_empty():
    db = _setup_generation_routes_db()
    try:
        db.query(GenerationHistoryModel).delete()
        db.query(GenerationStreamEventModel).delete()
        db.commit()
        history_page = asyncio.run(get_generation_history(db))
        assert history_page.items == []
        assert history_page.total == 0
        assert history_page.latest_event_id == 0
    finally:
        db.close()


def test_history_and_task_updates_append_stream_events():
    db = _setup_generation_routes_db()
    try:
        db.query(GenerationStreamEventModel).delete()
        db.query(GenerationHistoryModel).delete()
        db.query(GenerationTaskModel).delete()
        db.commit()

        history = upsert_history_entry(
            db,
            "task-stream-1",
            generation_type="manual",
            status="RUNNING",
            title="Streaming history",
            summary="Initial snapshot",
            source_asset_ids="[]",
            config_json="{}",
            task_step="running",
        )
        task = update_task(db, "task-stream-1", status="running", step="selecting_asset", progress=0.25)

        events = db.query(GenerationStreamEventModel).order_by(GenerationStreamEventModel.id.asc()).all()

        assert history.task_id == "task-stream-1"
        assert task.task_id == "task-stream-1"
        assert len(events) >= 2
        assert [event.event_type for event in events[:2]] == ["history-upsert", "task-upsert"]
        assert get_latest_event_id(db) == events[-1].id
    finally:
        db.close()


def test_stream_replay_gap_detection():
    db = _setup_generation_routes_db()
    try:
        db.query(GenerationStreamEventModel).delete()
        db.commit()

        db.add_all(
            [
                GenerationStreamEventModel(event_type="history-upsert", task_id="a", payload_json="{}"),
                GenerationStreamEventModel(event_type="task-upsert", task_id="a", payload_json="{}"),
                GenerationStreamEventModel(event_type="history-upsert", task_id="b", payload_json="{}"),
            ]
        )
        db.commit()

        assert replay_gap_requires_resync(db, 0) is False
        assert replay_gap_requires_resync(db, 1) is False
        rows = db.query(GenerationStreamEventModel).order_by(GenerationStreamEventModel.id.asc()).all()
        for row in rows[:2]:
            db.delete(row)
        db.commit()

        assert replay_gap_requires_resync(db, 1) is True
    finally:
        db.close()


def test_task_status_returns_new_contract():
    db = _setup_generation_routes_db()
    try:
        db.query(GenerationTaskModel).delete()
        db.commit()
        db.add(make_generation_task_row(task_id="task-status-1"))
        db.commit()

        payload = asyncio.run(get_task_status("task-status-1", db))

        assert payload.task_id == "task-status-1"
        assert payload.status == "running"
        assert payload.step == "selecting_asset"
        assert payload.progress == 0.35
        assert payload.done is False
        assert payload.error is None
        assert payload.created_at is not None
        assert payload.updated_at is not None
    finally:
        db.close()


def test_generation_history_returns_entry():
    db = _setup_generation_routes_db()
    try:
        db.query(GenerationHistoryModel).delete()
        db.commit()
        _add_history_row(db, "task-123")
        history_page = asyncio.run(get_generation_history(db))
        assert len(history_page.items) == 1
        assert history_page.items[0].task_id == "task-123"
        assert history_page.items[0].status == "PENDING_REVIEW"
        assert history_page.total == 1
        assert history_page.latest_event_id >= 0
    finally:
        db.close()


def test_generation_modules_endpoint_lists_new_effects():
    db = _setup_generation_routes_db()
    try:
        modules = asyncio.run(list_generation_modules())
        names = {module.name for module in modules}
        assert {
            "collage",
            "instafilter",
            "apple_weather",
            "filmstrip",
            "popart",
            "duotone",
            "halftone",
            "glitch",
            "light_leak",
            "neon_bloom",
            "cyanotype",
            "polaroid",
            "prism_split",
            "paper_cutout",
            "ai_caricature",
            "ai_anime",
            "ai_cinematic_3d_toy",
            "ai_collectible_figure",
            "ai_fantasy_hero",
            "ai_high_fashion_editorial",
            "ai_brick_built_figure",
            "ai_yellow_cartoon_sitcom",
        } <= names
        collage = next(module for module in modules if module.name == "collage")
        assert collage.config_schema and collage.config_schema[0].key == "styles"
    finally:
        db.close()


def test_reject_generation(tmp_path):
    db = _setup_generation_routes_db()
    try:
        _add_history_row(db, "task-reject")
        result = asyncio.run(reject_generation("task-reject", db))
        assert result.status == "REJECTED"
        assert result.task_id == "task-reject"
    finally:
        db.close()


def test_reject_generation_not_found():
    db = _setup_generation_routes_db()
    try:
        import pytest
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(reject_generation("nonexistent", db))
        assert exc_info.value.status_code == 404
    finally:
        db.close()


def test_reject_already_uploaded():
    from datetime import datetime, timezone

    db = _setup_generation_routes_db()
    try:
        row = _add_history_row(db, "task-already-uploaded", status="UPLOADED")
        row.accepted_at = datetime.now(timezone.utc)
        db.commit()

        import pytest
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(reject_generation("task-already-uploaded", db))
        assert exc_info.value.status_code == 409
    finally:
        db.close()


def test_get_generation_image(tmp_path, monkeypatch):
    import app.config

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app.config.get_settings.cache_clear()
    db = _setup_generation_routes_db()
    try:
        img_path = tmp_path / "task-img.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        _add_history_row(db, "task-img", output_path=str(img_path))

        response = get_generation_image("task-img", db=db)
        assert response.path == img_path
    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        app.config.get_settings.cache_clear()
        db.close()


def test_get_generation_image_not_found():
    db = _setup_generation_routes_db()
    try:
        import pytest
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_generation_image("no-such-task", db=db)
        assert exc_info.value.status_code == 404
    finally:
        db.close()


def test_get_generation_image_accepts_review_token_when_review_auth_enabled(monkeypatch, tmp_path):
    import pytest
    from fastapi import HTTPException

    import app.config
    from app.security import create_review_token

    monkeypatch.setenv("APP_ACCESS_TOKEN", "full-access-token")
    monkeypatch.setenv("REQUIRE_AUTH_FOR_REVIEW", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app.config.get_settings.cache_clear()

    db = _setup_generation_routes_db()
    try:
        img_path = tmp_path / "task-review-token.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        _add_history_row(db, "task-review-token", output_path=str(img_path))
        review_token = create_review_token("task-review-token")

        response = get_generation_image("task-review-token", review_token=review_token, db=db)

        assert response.path == img_path

        with pytest.raises(HTTPException) as exc_info:
            get_generation_image("task-review-token", review_token="bad-token", db=db)
        assert exc_info.value.status_code == 401
    finally:
        monkeypatch.delenv("APP_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("REQUIRE_AUTH_FOR_REVIEW", raising=False)
        monkeypatch.delenv("DATA_DIR", raising=False)
        app.config.get_settings.cache_clear()
        db.close()


def test_accept_generation(tmp_path, monkeypatch):
    from io import BytesIO

    from PIL import Image

    import app.config
    from app.schemas.generation import GenerationAcceptRequest

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app.config.get_settings.cache_clear()
    db = _setup_generation_routes_db()
    try:
        # Create a real PNG file
        img_path = tmp_path / "task-accept.png"
        buf = BytesIO()
        Image.new("RGB", (10, 10)).save(buf, format="PNG")
        img_path.write_bytes(buf.getvalue())

        _add_history_row(db, "task-accept", output_path=str(img_path))

        # Ensure settings row exists
        from app.services.immich import get_or_create_settings

        get_or_create_settings(db)
        db.commit()

        upload_result = MagicMock()
        upload_result.id = "immich-asset-id-1"
        upload_result.status = "created"

        tag_mock = MagicMock()
        tag_mock.id = "tag-id-1"

        fake_client = AsyncMock()
        fake_client.upload_asset = AsyncMock(return_value=upload_result)
        fake_client.list_albums = AsyncMock(return_value=[])
        fake_client.test_connection = AsyncMock(return_value=MagicMock(user_id="user-1"))
        mock_album = MagicMock()
        mock_album.id = "created-album-id-1"
        mock_album.album_name = "AI Photos"
        fake_client.create_album = AsyncMock(return_value=mock_album)
        fake_client.ensure_tag = AsyncMock(return_value=tag_mock)
        fake_client.tag_assets = AsyncMock()

        with patch("app.api.routes_generation_actions.build_immich_client", return_value=fake_client):
            req = GenerationAcceptRequest(create_album=False, album_name="AI Photos", album_id=None)
            result = asyncio.run(accept_generation("task-accept", req, db))

        assert result.status == "UPLOADED"
        assert result.uploaded_asset_id == "immich-asset-id-1"
        assert result.accepted_at is not None
    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        app.config.get_settings.cache_clear()
        db.close()


def test_accept_generation_records_partial_warnings(tmp_path, monkeypatch):
    from io import BytesIO

    from PIL import Image

    import app.config
    from app.immich.errors import ImmichError
    from app.schemas.generation import GenerationAcceptRequest

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app.config.get_settings.cache_clear()
    db = _setup_generation_routes_db()
    try:
        img_path = tmp_path / "task-accept-warn.png"
        buf = BytesIO()
        Image.new("RGB", (10, 10)).save(buf, format="PNG")
        img_path.write_bytes(buf.getvalue())

        _add_history_row(db, "task-accept-warn", output_path=str(img_path))

        get_or_create_settings(db)
        db.commit()

        upload_result = MagicMock()
        upload_result.id = "immich-asset-id-2"
        upload_result.status = "created"

        fake_client = AsyncMock()
        fake_client.upload_asset = AsyncMock(return_value=upload_result)
        fake_client.list_albums = AsyncMock(side_effect=ImmichError("albums endpoint unavailable"))
        fake_client.ensure_tag = AsyncMock(side_effect=ImmichError("tag endpoint unavailable"))

        with patch("app.api.routes_generation_actions.build_immich_client", return_value=fake_client):
            req = GenerationAcceptRequest(create_album=False, album_name="AI Photos", album_id=None)
            result = asyncio.run(accept_generation("task-accept-warn", req, db))

        assert result.status == "UPLOADED"
        assert result.accept_notes is not None
        assert "Album update failed" in result.accept_notes
        assert "Tagging failed" in result.accept_notes
    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        app.config.get_settings.cache_clear()
        db.close()


def test_retry_acceptance_replays_album_and_tag(tmp_path):
    from datetime import datetime, timezone

    db = _setup_generation_routes_db()
    try:
        row = _add_history_row(db, "task-retry", output_path=str(tmp_path / "retry.png"), status="UPLOADED")
        row.uploaded_asset_id = "immich-asset-id-3"
        row.album_name = "AI Photos"
        row.accept_notes = "Album update failed: temporary outage\nTagging failed: temporary outage"
        row.accepted_at = datetime.now(timezone.utc)
        db.commit()

        album = MagicMock()
        album.id = "album-id-1"
        album.album_name = "AI Photos"
        album.asset_count = 1
        album.thumbnail_asset_id = None

        tag_mock = MagicMock()
        tag_mock.id = "tag-id-1"

        fake_client = AsyncMock()
        fake_client.list_albums = AsyncMock(return_value=[album])
        fake_client.add_assets_to_album = AsyncMock()
        fake_client.ensure_tag = AsyncMock(return_value=tag_mock)
        fake_client.tag_assets = AsyncMock()

        with patch("app.api.routes_generation_actions.build_immich_client", return_value=fake_client):
            result = asyncio.run(retry_acceptance("task-retry", db))

        assert result.album_id == "album-id-1"
        assert result.album_updated is True
        assert result.accept_notes is None
        assert result.uploaded_asset_id == "immich-asset-id-3"
    finally:
        db.close()


def test_get_review_page():
    result = asyncio.run(get_review_page("task-review-test"))
    assert result is not None
    assert result.status_code == 200
    assert str(result.path).endswith("review.html")

    # Read the file and assert the new elements exist
    with open(result.path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "btn-toggle-original" in content
    assert "img-original" in content
    assert "lb-toggle-original" in content
    assert "lb-img-original" in content


def test_review_page_avoids_innerhtml_for_dynamic_api_values():
    result = asyncio.run(get_review_page("task-review-xss-test"))

    with open(result.path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "function createExifRow(iconSvg, label, value) {" in content
    create_exif_row = content.split("function createExifRow(iconSvg, label, value) {", 1)[1].split(
        "\nfunction renderProvenance", 1
    )[0]
    assert ".innerHTML" not in create_exif_row
    assert ".textContent" in create_exif_row

    render_timeline = content.split("function renderTimeline(taskTrace) {", 1)[1].split("\nfunction renderExif", 1)[0]
    assert "row.innerHTML" not in render_timeline
    assert "message.textContent" in render_timeline


def test_delete_history_by_status(tmp_path, monkeypatch):
    import app.config
    from app.api.routes_generation_actions import delete_history_by_status

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app.config.get_settings.cache_clear()
    db = _setup_generation_routes_db()
    try:
        # Add some mock rows with different statuses
        img_path_failed = tmp_path / "failed.png"
        img_path_failed.write_bytes(b"failed")
        _add_history_row(db, "task-failed", status="FAILED", output_path=str(img_path_failed))

        img_path_pending = tmp_path / "pending.png"
        img_path_pending.write_bytes(b"pending")
        _add_history_row(db, "task-pending", status="PENDING_REVIEW", output_path=str(img_path_pending))

        img_path_uploaded = tmp_path / "uploaded.png"
        img_path_uploaded.write_bytes(b"uploaded")
        _add_history_row(db, "task-uploaded", status="UPLOADED", output_path=str(img_path_uploaded))

        img_path_running = tmp_path / "running.png"
        img_path_running.write_bytes(b"running")
        _add_history_row(db, "task-running", status="RUNNING", output_path=str(img_path_running))

        # 1. Delete failed items
        asyncio.run(delete_history_by_status("failed", db))
        assert not img_path_failed.exists()
        assert img_path_pending.exists()
        assert img_path_uploaded.exists()
        assert img_path_running.exists()
        assert db.query(GenerationHistoryModel).filter(GenerationHistoryModel.status == "FAILED").count() == 0

        # 2. Delete pending items
        asyncio.run(delete_history_by_status("pending", db))
        assert not img_path_pending.exists()
        assert img_path_uploaded.exists()
        assert img_path_running.exists()
        assert db.query(GenerationHistoryModel).filter(GenerationHistoryModel.status == "PENDING_REVIEW").count() == 0

        # 3. Delete accepted (uploaded) items
        asyncio.run(delete_history_by_status("accepted", db))
        assert not img_path_uploaded.exists()
        assert img_path_running.exists()
        assert db.query(GenerationHistoryModel).filter(GenerationHistoryModel.status == "UPLOADED").count() == 0

        # 4. Delete running items
        asyncio.run(delete_history_by_status("running", db))
        assert not img_path_running.exists()
        assert db.query(GenerationHistoryModel).filter(GenerationHistoryModel.status == "RUNNING").count() == 0

    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        app.config.get_settings.cache_clear()
        db.close()


def test_generation_history_search_wildcard_escaping():
    db = _setup_generation_routes_db()
    try:
        db.query(GenerationHistoryModel).delete()
        db.commit()

        # Insert rows with wildcards
        _add_history_row(db, "task-1", status="PENDING_REVIEW")
        row1 = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == "task-1").first()
        row1.title = "photo%test"
        db.commit()

        _add_history_row(db, "task-2", status="PENDING_REVIEW")
        row2 = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == "task-2").first()
        row2.title = "photo_test"
        db.commit()

        _add_history_row(db, "task-3", status="PENDING_REVIEW")
        row3 = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == "task-3").first()
        row3.title = "photo\\test"
        db.commit()

        _add_history_row(db, "task-4", status="PENDING_REVIEW")
        row4 = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == "task-4").first()
        row4.title = "phototest"
        db.commit()

        from app.api.routes_generation import get_generation_history

        # Search literal "%"
        res = asyncio.run(get_generation_history(db, search="%"))
        assert len(res.items) == 1
        assert res.items[0].task_id == "task-1"

        # Search literal "_"
        res = asyncio.run(get_generation_history(db, search="_"))
        assert len(res.items) == 1
        assert res.items[0].task_id == "task-2"

        # Search literal "\\"
        res = asyncio.run(get_generation_history(db, search="\\"))
        assert len(res.items) == 1
        assert res.items[0].task_id == "task-3"

    finally:
        db.close()


def test_generation_history_filters_effect_liked_and_sort_order():
    db = _setup_generation_routes_db()
    try:
        db.query(EffectStatisticsLogModel).delete()
        db.query(GenerationHistoryModel).delete()
        db.commit()

        anime_old = _add_history_row(db, "task-anime-old", status="UPLOADED")
        anime_old.generation_type = "ai_anime"
        anime_old.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        anime_old.updated_at = anime_old.created_at
        db.add(EffectStatisticsLogModel(effect_id="ai_anime", task_id=anime_old.task_id, liked=True))

        anime_new = _add_history_row(db, "task-anime-new", status="UPLOADED")
        anime_new.generation_type = "ai_anime"
        anime_new.created_at = datetime(2026, 1, 3, tzinfo=timezone.utc)
        anime_new.updated_at = anime_new.created_at
        db.add(EffectStatisticsLogModel(effect_id="ai_anime", task_id=anime_new.task_id, liked=False))

        comic = _add_history_row(db, "task-comic", status="UPLOADED")
        comic.generation_type = "ai_comic_book"
        comic.created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
        comic.updated_at = comic.created_at
        db.add(EffectStatisticsLogModel(effect_id="ai_comic_book", task_id=comic.task_id, liked=True))
        db.commit()

        effect_res = asyncio.run(get_generation_history(db, status="UPLOADED", effect="ai_anime"))
        assert effect_res.total == 2
        assert [item.task_id for item in effect_res.items] == ["task-anime-new", "task-anime-old"]

        liked_res = asyncio.run(get_generation_history(db, status="UPLOADED", liked=True))
        assert liked_res.total == 2
        assert {item.task_id for item in liked_res.items} == {"task-comic", "task-anime-old"}

        oldest_res = asyncio.run(get_generation_history(db, status="UPLOADED", sort="oldest"))
        assert [item.task_id for item in oldest_res.items] == [
            "task-anime-old",
            "task-comic",
            "task-anime-new",
        ]

    finally:
        db.close()
