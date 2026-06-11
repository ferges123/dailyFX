from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from starlette.datastructures import QueryParams


def configure_contract_test_db(stem: str) -> Path:
    os.environ["APP_ENV"] = "development"
    os.environ["APP_SECRET_KEY"] = "test-api-secret"
    project_root = Path(__file__).resolve().parents[2]
    test_data_dir = project_root / "data" / "tests" / stem
    test_data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["DATA_DIR"] = str(test_data_dir)
    test_db = test_data_dir / "app.db"
    test_db.unlink(missing_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    return test_db


class FakeRequest:
    def __init__(self, query_string: str = "") -> None:
        self.query_params = QueryParams(query_string)


class FakePerson:
    def __init__(self, *, person_id: str = "person-1", name: str = "Alice", asset_count: int = 12) -> None:
        self.id = person_id
        self.name = name
        self.is_hidden = False
        self.asset_count = asset_count


class FakeAsset:
    def __init__(self) -> None:
        self.id = "asset-1"
        self.original_file_name = "photo.jpg"
        self.created_at = "2026-05-12T10:00:00Z"
        self.updated_at = None
        self.mime_type = "image/jpeg"
        self.asset_type = "IMAGE"
        self.people = [FakePerson()]


class FakeAssetPage:
    def __init__(self) -> None:
        self.items = [FakeAsset()]
        self.total = 1
        self.count = 1
        self.next_page = None


class FakeAlbum:
    def __init__(self) -> None:
        self.id = "album-1"
        self.album_name = "Trips"
        self.asset_count = 8
        self.thumbnail_asset_id = "asset-1"


class FakeImmichClient:
    async def search_assets(self, filters):
        self.filters = filters
        return FakeAssetPage()

    async def list_albums(self):
        return [FakeAlbum()]

    async def list_people(self):
        return [FakePerson()]


class FakeSettingsRow:
    def __init__(self) -> None:
        self.immich_url = "https://immich.example.test"
        self.debug_mode = False
        self.ai_vision_hourly_limit = 30
        self.ai_image_hourly_limit = 10
        self.favorite_albums_json = None
        self.ai_custom_prompt = None
        self.encrypted_immich_api_key = "immich-secret"
        self.encrypted_openai_api_key = "openai-secret"
        self.encrypted_gemini_api_key = "gemini-secret"
        self.encrypted_openrouter_api_key = "openrouter-secret"
        self.encrypted_byteplus_api_key = "byteplus-secret"
        self.encrypted_xiaomi_api_key = "xiaomi-secret"
        self.encrypted_local_ai_api_key = "local-secret"
        self.local_ai_base_url = "https://local-ai.example.test/v1"


def make_generation_history_row(
    *,
    task_id: str = "task-contract-1",
    generation_type: str = "collage",
    status: str = "PENDING_REVIEW",
    title: str = "Test collage",
    summary: str = "Created for route coverage",
    source_asset_ids: str = "[]",
    output_path: str | None = None,
    image_url: str | None = None,
    provider: str = "local",
    model: str = "pilgram+pil",
    total_token_count: int | None = None,
    config_json: str = "{}",
    tags_json: str | None = None,
    task_step: str | None = None,
    uploaded_asset_id: str | None = None,
    upload_status: str | None = None,
    album_id: str | None = None,
    album_name: str | None = None,
    album_created: bool = False,
    album_updated: bool = False,
    accept_notes: str | None = None,
    accepted_at: datetime | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> object:
    from app.models.generation_history import GenerationHistoryModel

    return GenerationHistoryModel(
        task_id=task_id,
        generation_type=generation_type,
        status=status,
        title=title,
        summary=summary,
        source_asset_ids=source_asset_ids,
        output_path=output_path,
        image_url=image_url or f"/api/generation/history/{task_id}/image",
        provider=provider,
        model=model,
        total_token_count=total_token_count,
        config_json=config_json,
        tags_json=tags_json,
        task_step=task_step,
        uploaded_asset_id=uploaded_asset_id,
        upload_status=upload_status,
        album_id=album_id,
        album_name=album_name,
        album_created=album_created,
        album_updated=album_updated,
        accept_notes=accept_notes,
        accepted_at=accepted_at,
        created_at=created_at or datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc),
        updated_at=updated_at or datetime(2026, 5, 12, 10, 1, tzinfo=timezone.utc),
    )


def make_generation_task_row(
    *,
    task_id: str = "task-contract-1",
    status: str = "running",
    step: str | None = "selecting_asset",
    progress: float | None = 0.35,
    error: str | None = None,
    payload_json: str = "{}",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> object:
    from app.models.generation_task import GenerationTaskModel

    return GenerationTaskModel(
        task_id=task_id,
        status=status,
        step=step,
        progress=progress,
        error=error,
        payload_json=payload_json,
        created_at=created_at or datetime(2026, 5, 12, 10, 5, tzinfo=timezone.utc),
        updated_at=updated_at or datetime(2026, 5, 12, 10, 6, tzinfo=timezone.utc),
    )


def make_notification_preset_row(
    *,
    name: str = "Notify",
    provider: str = "web",
    url: str | None = None,
    topic: str | None = None,
    encrypted_token: str | None = None,
    webhook_url: str | None = None,
) -> object:
    from app.models.notification_preset import NotificationPresetModel

    return NotificationPresetModel(
        name=name,
        provider=provider,
        url=url,
        topic=topic,
        encrypted_token=encrypted_token,
        webhook_url=webhook_url,
    )


def make_effect_preset_row(
    *,
    name: str = "Effect",
    groups_json: str = "[]",
) -> object:
    from app.models.effect_preset import EffectPresetModel

    return EffectPresetModel(
        name=name,
        groups_json=groups_json,
    )
