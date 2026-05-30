from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services.generation.upload_metadata import build_immich_upload_metadata


def test_build_immich_upload_metadata_prefers_source_timestamp_and_filename(tmp_path: Path) -> None:
    image_path = tmp_path / "generated.png"
    image_path.write_bytes(b"png-bytes")
    row = SimpleNamespace(
        title="My / Title",
        config_json='{"source_created_at":"2026-05-13T10:00:00+00:00","source_original_file_name":"photo.jpg"}',
    )

    metadata = build_immich_upload_metadata(row=row, task_id="task-123", image_path=image_path)

    assert metadata.filename == "photo_dailyFX.png"
    assert metadata.device_asset_id == "dailyFX-task-123"
    assert metadata.device_id == "dailyFX"
    assert metadata.file_created_at == "2026-05-13T10:00:00Z"
    assert metadata.file_modified_at == "2026-05-13T10:00:00Z"


def test_build_immich_upload_metadata_falls_back_to_task_title_and_file_mtime(tmp_path: Path) -> None:
    image_path = tmp_path / "generated.png"
    image_path.write_bytes(b"png-bytes")
    row = SimpleNamespace(title="My / Title", config_json="{}")

    metadata = build_immich_upload_metadata(row=row, task_id="task-456", image_path=image_path)

    assert metadata.filename == "My _ Title_dailyFX.png"
    assert metadata.device_asset_id == "dailyFX-task-456"
    assert metadata.device_id == "dailyFX"
    assert metadata.file_created_at.endswith("Z")
    assert metadata.file_modified_at == metadata.file_created_at
