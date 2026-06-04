from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.immich.models import ImmichUploadMetadata
from app.models.generation_history import GenerationHistoryModel


def build_immich_upload_metadata(
    *, row: GenerationHistoryModel, task_id: str, image_path: Path
) -> ImmichUploadMetadata:
    stat = image_path.stat()
    fallback_ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    config = json.loads(row.config_json or "{}")
    raw_ts = config.get("source_created_at")
    timestamp = raw_ts.replace("+00:00", "Z") if isinstance(raw_ts, str) and raw_ts else fallback_ts
    original_name = config.get("source_original_file_name")
    if original_name:
        stem = original_name.rsplit(".", 1)[0]
        filename = f"{stem}_dailyFX.png"
    else:
        filename = f"{row.title.strip().replace('/', '_') or task_id}_dailyFX.png"
    return ImmichUploadMetadata(
        filename=filename,
        device_asset_id=f"dailyFX-{task_id}",
        device_id="dailyFX",
        file_created_at=timestamp,
        file_modified_at=timestamp,
    )
