import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Initialize the test DB first before importing any app modules
from _contract_helpers import configure_contract_test_db

test_db = configure_contract_test_db("motion_pipeline")

from app.database import SessionLocal, init_db
from app.models.generation_history import GenerationHistoryModel
from app.schemas.generation import GenerationHistoryResponse
from app.services.generation.modules.base import GenerationResult
from app.services.generation.pipeline.metadata import _build_generation_artifacts
from app.services.generation.stream import serialize_history_row
from app.services.immich import get_or_create_settings


@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def settings(db_session):
    return get_or_create_settings(db_session)


def test_generation_result_defaults_to_png():
    result = GenerationResult(
        title="Static",
        summary="Static result",
        image_bytes=b"png",
        generation_type="test",
        provider="local",
        model="pil",
        config={},
        source_asset_ids=["asset-1"],
    )

    assert result.output_format == "png"
    assert result.frame_count is None


def test_history_response_includes_output_format():
    row = GenerationHistoryModel(
        id=1,
        task_id="task-1",
        generation_type="motion_pulse",
        status="PENDING_REVIEW",
        title="Motion",
        summary="Animated",
        source_asset_ids='["asset-1"]',
        output_path="/tmp/task-1.gif",
        image_url="/api/generation/history/task-1/image",
        provider="local",
        model="pil+imageio",
        config_json="{}",
        output_format="gif",
        frame_count=24,
        album_created=False,
        album_updated=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    response = GenerationHistoryResponse.from_model(row)

    assert response.output_format == "gif"
    assert response.frame_count == 24


def test_history_stream_snapshot_includes_output_format():
    row = GenerationHistoryModel(
        id=1,
        task_id="task-1",
        generation_type="motion_pulse",
        status="PENDING_REVIEW",
        title="Motion",
        summary="Animated",
        source_asset_ids="[]",
        output_path="/tmp/task-1.gif",
        image_url="/api/generation/history/task-1/image",
        provider="local",
        model="pil+imageio",
        config_json="{}",
        output_format="gif",
        frame_count=24,
    )

    snapshot = serialize_history_row(row)

    assert snapshot["output_format"] == "gif"
    assert snapshot["frame_count"] == 24


def test_generation_output_paths_use_output_format(tmp_path, monkeypatch):
    class FakeSettings:
        data_dir = tmp_path

    from app.services.generation import engine as engine_module

    monkeypatch.setattr(engine_module, "get_settings", lambda: FakeSettings())

    from app.services.generation.pipeline.persistence import _generation_output_paths

    gif_path, gif_url = _generation_output_paths("task-gif", "gif")
    png_path, png_url = _generation_output_paths("task-png", "png")

    assert Path(gif_path).name == "task-gif.gif"
    assert Path(png_path).name == "task-png.png"
    assert gif_url == "/api/generation/history/task-gif/image"
    assert png_url == "/api/generation/history/task-png/image"


@dataclass
class FakeResult:
    title: str = "Motion"
    summary: str = "Animated result"
    image_bytes: bytes = b"GIF89a animated bytes"
    generation_type: str = "motion_pulse"
    provider: str = "local"
    model: str = "pil+imageio"
    config: dict = None
    source_asset_ids: list[str] = None
    output_format: str = "gif"
    frame_count: int = 24

    def __post_init__(self):
        self.config = self.config or {}
        self.source_asset_ids = self.source_asset_ids or ["asset-1"]


@dataclass
class FakeAsset:
    id: str = "asset-1"
    original_file_name: str = "photo.jpg"
    created_at: str | None = None
    people: list = None

    def __post_init__(self):
        self.people = self.people or []


def test_metadata_enrichment_does_not_convert_animated_output(db_session, settings):
    client = AsyncMock()
    client.get_asset_exif = AsyncMock(return_value={"make": "DailyFX"})

    async def run_test():
        return await _build_generation_artifacts(
            db=db_session,
            client=client,
            source_asset=FakeAsset(),
            people_context=None,
            result=FakeResult(),
            module=object(),
            group_name="motion_pulse",
            settings=settings,
            task_id="task-motion",
            _task_update=lambda **kwargs: None,
            _progress=lambda message: None,
            photo_selection_trace=None,
        )

    artifacts = asyncio.run(run_test())

    assert artifacts.final_bytes == b"GIF89a animated bytes"
    assert artifacts.metadata_provenance["exif_info"]["attempted"] is True
    assert artifacts.metadata_provenance["exif_info"]["embedded"] is False
    assert artifacts.metadata_provenance["exif_info"]["skip_reason"] == "animated_output"


from fastapi.testclient import TestClient

from app.main import app
from app.security import require_auth


@pytest.fixture
def authenticated_client():
    app.dependency_overrides[require_auth] = lambda: None
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_history_image_uses_output_format_mime_type(authenticated_client, db_session, tmp_path):
    path = tmp_path / "task-gif.gif"
    path.write_bytes(b"GIF89a")
    row = GenerationHistoryModel(
        task_id="task-gif",
        generation_type="motion_pulse",
        status="PENDING_REVIEW",
        title="Motion",
        summary="Animated",
        source_asset_ids="[]",
        output_path=str(path),
        image_url="/api/generation/history/task-gif/image",
        provider="local",
        model="pil+imageio",
        config_json="{}",
        output_format="gif",
        frame_count=24,
        album_created=False,
        album_updated=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db_session.add(row)
    db_session.commit()

    response = authenticated_client.get("/api/generation/history/task-gif/image")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/gif")
    assert response.content.startswith(b"GIF")


def test_immich_upload_metadata_uses_output_format_extension(tmp_path):
    path = tmp_path / "task-gif.gif"
    path.write_bytes(b"GIF89a")
    row = GenerationHistoryModel(
        task_id="task-gif",
        generation_type="motion_pulse",
        status="PENDING_REVIEW",
        title="Motion/Result",
        summary="Animated",
        source_asset_ids="[]",
        output_path=str(path),
        image_url="/api/generation/history/task-gif/image",
        provider="local",
        model="pil+imageio",
        config_json='{"source_original_file_name": "source.jpg"}',
        output_format="gif",
        frame_count=24,
    )

    from app.services.generation.upload_metadata import build_immich_upload_metadata

    metadata = build_immich_upload_metadata(row=row, task_id="task-gif", image_path=path)

    assert metadata.filename == "source_dailyFX.gif"
    assert metadata.content_type == "image/gif"
