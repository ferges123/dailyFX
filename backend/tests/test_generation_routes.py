import asyncio
import json
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
    run_history_ai_vision,
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
        history_page = get_generation_history(db)
        assert history_page.items == []
        assert history_page.total == 0
        assert history_page.latest_event_id == 0
    finally:
        db.close()


def test_generation_history_pagination_bounds():
    from app.main import app

    parameters = app.openapi()["paths"]["/api/generation/history"]["get"]["parameters"]
    pagination = {parameter["name"]: parameter["schema"] for parameter in parameters}
    assert pagination["offset"]["minimum"] == 0
    assert pagination["limit"]["minimum"] == 1
    assert pagination["limit"]["maximum"] == 100


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


def test_load_events_after_bounded_limit():
    from app.services.generation.stream import load_events_after

    db = _setup_generation_routes_db()
    try:
        db.query(GenerationStreamEventModel).delete()
        db.commit()

        db.add_all(
            [
                GenerationStreamEventModel(event_type="test-event", task_id=f"t-{i}", payload_json="{}")
                for i in range(600)
            ]
        )
        db.commit()

        batch1 = load_events_after(db, 0)
        assert len(batch1) == 500
        assert batch1[0].task_id == "t-0"
        assert batch1[-1].task_id == "t-499"

        batch2 = load_events_after(db, batch1[-1].id)
        assert len(batch2) == 100
        assert batch2[0].task_id == "t-500"
        assert batch2[-1].task_id == "t-599"
    finally:
        db.close()


def test_prune_generation_stream_events():
    from app.services.generation.stream import prune_generation_stream_events

    db = _setup_generation_routes_db()
    try:
        db.query(GenerationStreamEventModel).delete()
        db.commit()

        db.add_all(
            [
                GenerationStreamEventModel(event_type="test-event", task_id=f"p-{i}", payload_json="{}")
                for i in range(10)
            ]
        )
        db.commit()

        deleted = prune_generation_stream_events(db, max_rows=5)
        db.commit()

        assert deleted == 5
        rows = db.query(GenerationStreamEventModel).order_by(GenerationStreamEventModel.id.asc()).all()
        assert len(rows) == 5
        assert [r.task_id for r in rows] == ["p-5", "p-6", "p-7", "p-8", "p-9"]

        # Cursor for pruned event p-2 receives resync-required
        pruned_cursor = rows[0].id - 2
        assert replay_gap_requires_resync(db, pruned_cursor) is True
    finally:
        db.close()


def test_task_status_returns_new_contract():
    db = _setup_generation_routes_db()
    try:
        db.query(GenerationTaskModel).delete()
        db.commit()
        db.add(make_generation_task_row(task_id="task-status-1"))
        db.commit()

        payload = get_task_status("task-status-1", db)

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
        history_page = get_generation_history(db)
        assert len(history_page.items) == 1
        assert history_page.items[0].task_id == "task-123"
        assert history_page.items[0].status == "PENDING_REVIEW"
        assert history_page.total == 1
        assert history_page.latest_event_id >= 0
    finally:
        db.close()


def test_generation_history_query_count_is_bounded():
    db = _setup_generation_routes_db()
    try:
        db.query(EffectStatisticsLogModel).delete()
        db.query(GenerationHistoryModel).delete()
        db.commit()

        for i in range(24):
            task_id = f"task-bound-{i}"
            _add_history_row(db, task_id)
            db.add(EffectStatisticsLogModel(effect_id="collage", task_id=task_id, liked=bool(i % 2)))
        db.commit()

        from sqlalchemy import event

        queries = []

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)

        event.listen(db.get_bind(), "before_cursor_execute", before_cursor_execute)
        try:
            page = get_generation_history(db, limit=24)
            assert len(page.items) == 24
            assert page.items[0].liked is not None
            assert len(queries) <= 4
        finally:
            event.remove(db.get_bind(), "before_cursor_execute", before_cursor_execute)
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
        result = reject_generation("task-reject", db)
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
            reject_generation("nonexistent", db)
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
            reject_generation("task-already-uploaded", db)
        assert exc_info.value.status_code == 409
    finally:
        db.close()


def test_history_ai_vision_updates_summary_tags_and_provenance(tmp_path, monkeypatch):
    import app.config
    from app.services.generation.ai_vision import AIVisionResult

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app.config.get_settings.cache_clear()
    db = _setup_generation_routes_db()
    try:
        image_path = tmp_path / "task-ai-vision.png"
        image_path.write_bytes(b"test image")
        row = _add_history_row(db, "task-ai-vision", output_path=str(image_path))
        row.title = "Original title"
        row.total_token_count = 7
        row.config_json = '{"metadata_provenance":{"tag_injections":["AI","Watercolor"]}}'
        db.commit()

        analysis = AIVisionResult(
            title="Luminous Painted Landscape",
            summary="A luminous painted landscape.",
            tags=["landscape", "sunset", "Landscape"],
            token_count=12,
            provider="openai",
            model="gpt-4o-mini",
        )
        with patch(
            "app.api.routes_generation_actions.analyze_image",
            new=AsyncMock(return_value=analysis),
        ), patch(
            "app.api.routes_generation_actions._prepare_history_ai_vision_data",
            return_value=(b"test image", MagicMock(default_ai_provider="openai")),
        ):
            result = asyncio.run(run_history_ai_vision("task-ai-vision", db))

        assert result.title == "Luminous Painted Landscape"
        assert result.summary == "A luminous painted landscape."
        assert result.tags_json == '["landscape", "sunset", "AI", "Watercolor"]'
        assert result.total_token_count == 19
        provenance = json.loads(result.config_json)["metadata_provenance"]
        assert provenance["title_source"] == "history_final_vision"
        assert provenance["summary_source"] == "history_final_vision"
        assert provenance["tags_source"] == "history_final_vision"
        assert provenance["final_vision"]["succeeded"] is True
        assert provenance["final_vision"]["provider"] == "openai"
        assert db.query(GenerationStreamEventModel).filter_by(task_id="task-ai-vision").count() >= 1
    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        app.config.get_settings.cache_clear()
        db.close()


def test_run_history_ai_vision_with_review_token(tmp_path, monkeypatch):
    import app.config
    from app.api.routes_generation_actions import run_history_ai_vision
    from app.security import create_review_token
    from app.services.generation.ai_vision import AIVisionResult

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("REQUIRE_AUTH_FOR_REVIEW", "true")
    app.config.get_settings.cache_clear()
    db = _setup_generation_routes_db()
    try:
        image_path = tmp_path / "task-ai-vision-review.png"
        image_path.write_bytes(b"test image")
        _add_history_row(db, "task-ai-vision-review", output_path=str(image_path))
        db.commit()

        token = create_review_token("task-ai-vision-review")

        analysis = AIVisionResult(
            title="Review Vision Title",
            summary="A review summary.",
            tags=["review", "vision"],
            token_count=5,
            provider="openai",
            model="gpt-4o-mini",
        )
        with patch(
            "app.api.routes_generation_actions.analyze_image",
            new=AsyncMock(return_value=analysis),
        ), patch(
            "app.api.routes_generation_actions._prepare_history_ai_vision_data",
            return_value=(b"test image", MagicMock(default_ai_provider="openai")),
        ):
            result = asyncio.run(
                run_history_ai_vision("task-ai-vision-review", review_token=token, db=db)
            )

        assert result.title == "Review Vision Title"
        assert result.summary == "A review summary."
    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        monkeypatch.delenv("REQUIRE_AUTH_FOR_REVIEW", raising=False)
        app.config.get_settings.cache_clear()
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
    assert "btn-ai-vision" in content


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
        delete_history_by_status("failed", db)
        assert not img_path_failed.exists()
        assert img_path_pending.exists()
        assert img_path_uploaded.exists()
        assert img_path_running.exists()
        assert db.query(GenerationHistoryModel).filter(GenerationHistoryModel.status == "FAILED").count() == 0

        # 2. Delete pending items
        delete_history_by_status("pending", db)
        assert not img_path_pending.exists()
        assert img_path_uploaded.exists()
        assert img_path_running.exists()
        assert db.query(GenerationHistoryModel).filter(GenerationHistoryModel.status == "PENDING_REVIEW").count() == 0

        # 3. Delete accepted (uploaded) items
        delete_history_by_status("accepted", db)
        assert not img_path_uploaded.exists()
        assert img_path_running.exists()
        assert db.query(GenerationHistoryModel).filter(GenerationHistoryModel.status == "UPLOADED").count() == 0

        # 4. Delete running items
        delete_history_by_status("running", db)
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
        res = get_generation_history(db, search="%")
        assert len(res.items) == 1
        assert res.items[0].task_id == "task-1"

        # Search literal "_"
        res = get_generation_history(db, search="_")
        assert len(res.items) == 1
        assert res.items[0].task_id == "task-2"

        # Search literal "\\"
        res = get_generation_history(db, search="\\")
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

        effect_res = get_generation_history(db, status="UPLOADED", effect="ai_anime")
        assert effect_res.total == 2
        assert [item.task_id for item in effect_res.items] == ["task-anime-new", "task-anime-old"]

        liked_res = get_generation_history(db, status="UPLOADED", liked=True)
        assert liked_res.total == 2
        assert {item.task_id for item in liked_res.items} == {"task-comic", "task-anime-old"}

        oldest_res = get_generation_history(db, status="UPLOADED", sort="oldest")
        assert [item.task_id for item in oldest_res.items] == [
            "task-anime-old",
            "task-comic",
            "task-anime-new",
        ]

    finally:
        db.close()


def test_generation_history_filters_schedule_id():
    db = _setup_generation_routes_db()
    try:
        db.query(GenerationHistoryModel).delete()
        db.commit()

        sched1 = _add_history_row(db, "task-sched1", status="UPLOADED")
        sched1.schedule_id = 10
        sched2 = _add_history_row(db, "task-sched2", status="UPLOADED")
        sched2.schedule_id = 20
        manual = _add_history_row(db, "task-manual", status="UPLOADED")
        manual.schedule_id = None
        db.commit()

        # Specific schedule
        s10_res = get_generation_history(db, status="UPLOADED", schedule_id=10)
        assert s10_res.total == 1
        assert s10_res.items[0].task_id == "task-sched1"
        assert s10_res.items[0].schedule_id == 10

        # Manual / studio (-1)
        manual_res = get_generation_history(db, status="UPLOADED", schedule_id=-1)
        assert manual_res.total == 1
        assert manual_res.items[0].task_id == "task-manual"
        assert manual_res.items[0].schedule_id is None

        # All schedules (None)
        all_res = get_generation_history(db, status="UPLOADED")
        assert all_res.total == 3
    finally:
        db.close()
