"""One-off repair for generated images that missed source metadata.

Run from ``backend``:
    .venv/bin/python scripts/repair_missing_generation_metadata.py --dry-run
    .venv/bin/python scripts/repair_missing_generation_metadata.py --apply --update-immich
"""

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if os.environ.get("DATABASE_URL") == "sqlite:////data/app.db" or not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = f"sqlite:///{PROJECT_ROOT / 'data' / 'app.db'}"

from app.database import SessionLocal, init_db
from app.models.generation_history import GenerationHistoryModel
from app.services.generation.exif_embedder import embed_exif_metadata
from app.services.immich import build_immich_client, get_or_create_settings

logger = logging.getLogger(__name__)
RESULTS_DIR = PROJECT_ROOT / "data" / "results"


def _local_output_path(output_path: str | None) -> Path | None:
    if not output_path:
        return None
    path = Path(output_path)
    if path.is_absolute() and str(path).startswith("/data/results/"):
        return RESULTS_DIR / path.name
    return path


def _source_asset_id(row: GenerationHistoryModel) -> str | None:
    try:
        source_ids = json.loads(row.source_asset_ids)
    except (TypeError, json.JSONDecodeError):
        return None
    return source_ids[0] if isinstance(source_ids, list) and source_ids and isinstance(source_ids[0], str) else None


def _source_timestamp(payload: dict) -> str | None:
    value = payload.get("fileCreatedAt") or payload.get("createdAt")
    return value if isinstance(value, str) and value else None


def _metadata_was_skipped(row: GenerationHistoryModel) -> bool:
    try:
        config = json.loads(row.config_json or "{}")
    except json.JSONDecodeError:
        return False
    provenance = config.get("metadata_provenance")
    exif_state = provenance.get("exif_info") if isinstance(provenance, dict) else None
    return isinstance(exif_state, dict) and exif_state.get("attempted") is False


def _metadata_was_repaired(row: GenerationHistoryModel) -> bool:
    try:
        config = json.loads(row.config_json or "{}")
    except json.JSONDecodeError:
        return False
    provenance = config.get("metadata_provenance")
    exif_state = provenance.get("exif_info") if isinstance(provenance, dict) else None
    return isinstance(exif_state, dict) and exif_state.get("repaired") is True


async def repair(*, apply: bool, update_immich: bool) -> dict[str, int]:
    counters = {
        "candidates": 0,
        "repaired": 0,
        "immich_dates_updated": 0,
        "missing_files": 0,
        "source_errors": 0,
    }
    init_db()
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        client = build_immich_client(settings)
        rows = [
            row
            for row in db.query(GenerationHistoryModel).all()
            if _metadata_was_skipped(row) or (update_immich and row.uploaded_asset_id and _metadata_was_repaired(row))
        ]
        counters["candidates"] = len(rows)

        for row in rows:
            needs_local_repair = _metadata_was_skipped(row)
            output_path = _local_output_path(row.output_path)
            source_id = _source_asset_id(row)
            if needs_local_repair and (output_path is None or not output_path.is_file()):
                counters["missing_files"] += 1
                logger.warning("Skipping %s: local output is unavailable", row.task_id)
                continue
            if not source_id:
                counters["source_errors"] += 1
                logger.warning("Skipping %s: source asset ID is unavailable", row.task_id)
                continue

            try:
                source = await client.get_asset_info(source_id)
                exif_info = source.get("exifInfo") or {}
                created_at = _source_timestamp(source) or exif_info.get("dateTimeOriginal")
                original_name = source.get("originalFileName")
                if not isinstance(exif_info, dict):
                    raise ValueError("Immich returned a non-object exifInfo")
            except Exception as exc:
                counters["source_errors"] += 1
                logger.warning("Skipping %s: unable to fetch source metadata: %s", row.task_id, exc)
                continue

            if apply and needs_local_repair:
                final_bytes = embed_exif_metadata(output_path.read_bytes(), None, row.title, exif_info)
                temp_path = output_path.with_suffix(f"{output_path.suffix}.metadata-repair")
                temp_path.write_bytes(final_bytes)
                temp_path.replace(output_path)

                config = json.loads(row.config_json or "{}")
                provenance = config.setdefault("metadata_provenance", {})
                provenance["exif_info"] = {
                    "attempted": True,
                    "embedded": True,
                    "skip_reason": None,
                    "repaired": True,
                }
                config["exif"] = exif_info
                if created_at:
                    config["source_created_at"] = created_at.replace("+00:00", "Z")
                if isinstance(original_name, str) and original_name:
                    config["source_original_file_name"] = original_name
                config["metadata_repaired_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                row.config_json = json.dumps(config)
            if needs_local_repair:
                counters["repaired"] += 1
                logger.info("%s local metadata for %s", "Repaired" if apply else "Would repair", row.task_id)

            if update_immich and row.uploaded_asset_id and created_at:
                if apply:
                    await client.update_assets_datetime_original([row.uploaded_asset_id], created_at)
                counters["immich_dates_updated"] += 1
                logger.info("%s Immich date for %s", "Updated" if apply else "Would update", row.task_id)

        if apply:
            db.commit()
        return counters
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair missing source metadata in DailyFX generation history.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Inspect repairable records without changing files or data.")
    mode.add_argument("--apply", action="store_true", help="Apply the one-off local file and history repair.")
    parser.add_argument(
        "--update-immich",
        action="store_true",
        help="Also update DateTimeOriginal on already uploaded Immich assets.",
    )
    args = parser.parse_args()
    if args.update_immich and not args.apply:
        parser.error("--update-immich requires --apply")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    counters = asyncio.run(repair(apply=args.apply, update_immich=args.update_immich))
    print(json.dumps(counters, sort_keys=True))


if __name__ == "__main__":
    main()
