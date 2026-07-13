import asyncio
from datetime import datetime, timezone

from _contract_helpers import configure_contract_test_db, make_generation_history_row, make_generation_task_row

from app.api.routes_generation import get_generation_history, get_task_status
from app.database import SessionLocal, init_db
from app.models.effect_preset import EffectPresetModel
from app.models.filter_preset import FilterPresetModel
from app.models.generation_history import GenerationHistoryModel
from app.models.generation_stream_event import GenerationStreamEventModel
from app.models.generation_task import GenerationTaskModel
from app.models.notification_preset import NotificationPresetModel
from app.models.schedule import ScheduleModel
from app.schemas.generation import GenerationHistoryPage

test_db = configure_contract_test_db("api_contracts_generation")


def test_task_status_contract():
    init_db()
    db = SessionLocal()
    try:
        db.query(GenerationTaskModel).delete()
        db.commit()

        db.add(make_generation_task_row(task_id="task-contract-1"))
        db.commit()

        payload = asyncio.run(get_task_status("task-contract-1", db))
        assert payload.model_dump(mode="json") == {
            "task_id": "task-contract-1",
            "status": "running",
            "step": "selecting_asset",
            "progress": 0.35,
            "done": False,
            "error": None,
            "created_at": "2026-05-12T10:05:00Z",
            "updated_at": "2026-05-12T10:06:00Z",
        }
    finally:
        db.close()


def test_generation_history_contract():
    init_db()
    db = SessionLocal()
    try:
        db.query(GenerationHistoryModel).delete()
        db.query(GenerationStreamEventModel).delete()
        db.query(ScheduleModel).delete()
        db.query(NotificationPresetModel).delete()
        db.query(FilterPresetModel).delete()
        db.query(EffectPresetModel).delete()
        db.commit()

        row = make_generation_history_row(
            task_id="task-contract-1",
            generation_type="schedule_run",
            status="UPLOADED",
            title="Contract title",
            summary="Contract summary",
            source_asset_ids='["asset-1"]',
            output_path="/tmp/output.png",
            image_url="/api/generation/history/task-contract-1/image",
            provider="openai",
            model="gpt-4o",
            total_token_count=42,
            config_json='{"source":"contract"}',
            tags_json='["tag-1","tag-2"]',
            task_step="uploading",
            uploaded_asset_id="immich-asset-1",
            upload_status="success",
            album_id="album-1",
            album_name="Album Contract",
            album_created=True,
            album_updated=False,
            accept_notes="Uploaded successfully",
            accepted_at=datetime(2026, 5, 12, 10, 30, tzinfo=timezone.utc),
            created_at=datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 5, 12, 10, 31, tzinfo=timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        payload = asyncio.run(get_generation_history(db))
        contract = GenerationHistoryPage.model_validate(payload).model_dump(mode="json")

        assert contract == {
            "items": [
                {
                    "id": row.id,
                    "task_id": "task-contract-1",
                    "generation_type": "schedule_run",
                    "status": "UPLOADED",
                    "title": "Contract title",
                    "summary": "Contract summary",
                    "source_asset_ids": '["asset-1"]',
                    "output_path": "/tmp/output.png",
                    "image_url": f"/api/generation/history/task-contract-1/image?t={int(row.updated_at.timestamp())}",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "total_token_count": 42,
                    "config_json": '{"source":"contract"}',
                    "tags_json": '["tag-1","tag-2"]',
                    "task_step": "uploading",
                    "uploaded_asset_id": "immich-asset-1",
                    "upload_status": "success",
                    "album_id": "album-1",
                    "album_name": "Album Contract",
                    "album_created": True,
                    "album_updated": False,
                    "accept_notes": "Uploaded successfully",
                    "accepted_at": "2026-05-12T10:30:00Z",
                    "output_format": "png",
                    "frame_count": None,
                    "created_at": "2026-05-12T10:00:00Z",
                    "updated_at": "2026-05-12T10:31:00Z",
                    "liked": None,
                    "local_file_status": "available",
                    "local_file_deleted_at": None,
                    "local_file_delete_reason": None,
                }
            ],
            "total": 1,
            "latest_event_id": 0,
        }
    finally:
        db.close()
        test_db.unlink(missing_ok=True)
