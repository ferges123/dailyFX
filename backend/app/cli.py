from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models.effect_preset import EffectPresetModel
from app.models.filter_preset import FilterPresetModel
from app.models.generation_history import GenerationHistoryModel
from app.models.schedule import ScheduleModel
from app.services.generation.engine import run_generation_cycle
from app.services.generation.history import upsert_history_entry
from app.services.generation.host_manifest import HOST_METADATA_SOURCE
from app.services.generation.run_now import preview_run_now_assets, record_run_now_failure_history
from app.services.generation.schedule_runs import build_scheduled_run_context
from app.services.generation.tasks import ensure_task, update_task
from app.services.immich import build_immich_client, get_or_create_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HandoffManifest:
    task_id: str
    status: str
    image_path: str
    generation_type: str
    title: str
    summary: str
    tags: list[str]
    provider: str | None
    model: str | None
    source_asset_ids: list[str]
    schedule_id: int | None
    album_name: str | None
    output_format: str | None
    frame_count: int | None
    metadata_provenance: dict[str, object] | None
    handoff_prompt: str
    task_trace: list[object] = field(default_factory=list)


@dataclass(frozen=True)
class HostRenderManifest:
    task_id: str
    schedule_id: int
    target: str
    generation_type: str
    title: str
    summary: str
    prompt: str
    source_image_path: str
    source_asset_id: str
    source_asset_original_file_name: str | None
    output_path: str
    config_json: dict[str, object]
    source_asset_created_at: str | None
    task_trace: list[object]
    handoff_prompt: str


class CLIError(RuntimeError):
    pass


def _to_iso_timestamp(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
        except ValueError:
            return text
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="dailyfx")
    subparsers = parser.add_subparsers(dest="command", required=True)

    schedules = subparsers.add_parser("schedules", help="List schedule IDs and names")
    schedules.add_argument("--json", action="store_true", help="Emit JSON instead of a table")

    generate = subparsers.add_parser("generate", help="Run one scheduled DailyFX generation now")
    generate.add_argument("--schedule-id", type=int, required=True, help="Schedule ID to execute")
    generate.add_argument("--task-id", type=str, default=None, help="Optional explicit task ID")
    generate.add_argument(
        "--handoff-json",
        action="store_true",
        help="Emit machine-readable handoff JSON for host wrappers",
    )

    host_prepare = subparsers.add_parser(
        "prepare-host",
        help="Prepare a host-run image generation manifest for agy/codex",
    )
    host_prepare.add_argument("--schedule-id", type=int, required=True, help="Schedule ID to execute")
    host_prepare.add_argument("--task-id", type=str, default=None, help="Optional explicit task ID")
    host_prepare.add_argument(
        "--target",
        choices=["agy", "codex"],
        required=True,
        help="Host target that will generate the final image",
    )

    host_finalize = subparsers.add_parser(
        "finalize-host",
        help="Finalize a host-run generation after agy/codex wrote the output image",
    )
    host_finalize.add_argument("--manifest-path", type=str, required=True, help="Path to the host render manifest")

    return parser.parse_args(argv)


def _load_schedule_context(db: Session, schedule_id: int):
    schedule = db.get(ScheduleModel, schedule_id)
    if schedule is None:
        raise CLIError(f"Schedule {schedule_id} not found")

    filter_preset = db.get(FilterPresetModel, schedule.filter_preset_id)
    effect_preset = db.get(EffectPresetModel, schedule.effect_preset_id)
    if filter_preset is None or effect_preset is None:
        raise CLIError(f"Schedule {schedule_id} has missing presets")

    notification_presets = list(schedule.notification_presets)
    run_context = build_scheduled_run_context(
        schedule_id=schedule_id,
        album_name=schedule.album_name,
        filter_preset=filter_preset,
        effect_preset=effect_preset,
        notification_presets=notification_presets,
    )
    return schedule, run_context, notification_presets


def _load_history_row(db: Session, task_id: str) -> GenerationHistoryModel:
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    if row is None:
        raise CLIError(f"Generation history entry for task {task_id} was not created")
    return row


def _list_schedules(db: Session, as_json: bool = False) -> None:
    rows = db.query(ScheduleModel).order_by(ScheduleModel.name).all()
    items = [{"id": row.id, "name": row.name, "enabled": row.enabled} for row in rows]
    if as_json:
        json.dump(items, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    if not items:
        print("No schedules found")
        return

    print("ID\tNAME\tENABLED")
    for item in items:
        enabled = "yes" if item["enabled"] else "no"
        print(f"{item['id']}\t{item['name']}\t{enabled}")


def _parse_json_value(payload: str | None) -> object:
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except Exception:
        return {}


def _parse_json_object(payload: str | None) -> dict[str, object]:
    parsed = _parse_json_value(payload)
    return parsed if isinstance(parsed, dict) else {}


def _parse_host_metadata(
    payload: dict[str, object], original_manifest: dict[str, object] | None = None
) -> tuple[str, str, list[str]]:
    from app.services.generation.host_manifest import (
        ManifestValidationError,
        validate_and_normalize_host_manifest,
    )

    try:
        normalized = validate_and_normalize_host_manifest(payload, original_manifest)
    except ManifestValidationError as e:
        raise CLIError(str(e)) from e

    return normalized["title"], normalized["summary"], normalized["tags"]


def _build_handoff_prompt(
    *,
    task_id: str,
    generation_type: str,
    title: str,
    summary: str,
    tags: list[str],
    source_asset_ids: list[str],
) -> str:
    tags_text = ", ".join(tags) if tags else "none"
    source_text = ", ".join(source_asset_ids) if source_asset_ids else "none"
    return (
        "You are continuing from a DailyFX-generated image.\n"
        f"Task ID: {task_id}\n"
        f"Generation type: {generation_type}\n"
        f"Title: {title}\n"
        f"Summary: {summary}\n"
        f"Tags: {tags_text}\n"
        f"Source asset IDs: {source_text}\n"
        "Use the attached image as the starting point and continue with the requested analysis or edit."
    )


def _build_manifest(row: GenerationHistoryModel) -> HandoffManifest:
    source_asset_ids = _parse_json_value(row.source_asset_ids)
    tags = _parse_json_value(row.tags_json)
    config = _parse_json_object(row.config_json)
    metadata_provenance = config.get("metadata_provenance")
    task_trace = config.get("task_trace")

    image_path = row.output_path
    if not image_path:
        raise CLIError(f"History entry for task {row.task_id} has no output path")

    return HandoffManifest(
        task_id=row.task_id,
        status=row.status,
        image_path=image_path,
        generation_type=row.generation_type,
        title=row.title,
        summary=row.summary,
        tags=tags if isinstance(tags, list) else [],
        provider=row.provider,
        model=row.model,
        source_asset_ids=source_asset_ids if isinstance(source_asset_ids, list) else [],
        schedule_id=row.schedule_id,
        album_name=row.album_name,
        output_format=row.output_format,
        frame_count=row.frame_count,
        metadata_provenance=metadata_provenance if isinstance(metadata_provenance, dict) else None,
        task_trace=task_trace if isinstance(task_trace, list) else [],
        handoff_prompt=_build_handoff_prompt(
            task_id=row.task_id,
            generation_type=row.generation_type,
            title=row.title,
            summary=row.summary,
            tags=tags if isinstance(tags, list) else [],
            source_asset_ids=source_asset_ids if isinstance(source_asset_ids, list) else [],
        ),
    )


def _build_host_render_prompt(*, task_id: str, generation_type: str, title: str, summary: str) -> str:
    return (
        "Generate the final image locally using the attached source photo.\n"
        f"Task ID: {task_id}\n"
        f"Generation type: {generation_type}\n"
        f"Title: {title}\n"
        f"Summary: {summary}\n"
        "Write the result to the provided output path."
    )


def _host_render_paths(task_id: str) -> tuple[Path, Path]:
    from app.config import get_settings

    results_dir = get_settings().data_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    source_path = results_dir / f"{task_id}.input.png"
    output_path = results_dir / f"{task_id}.png"
    return source_path, output_path


def _asset_summary_to_namespace(asset: object, people: list[dict[str, object]] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=getattr(asset, "id", None),
        original_file_name=getattr(asset, "original_file_name", None),
        created_at=getattr(asset, "created_at", None),
        people=people or getattr(asset, "people", None) or [],
    )


def _host_render_manifest_from_request(
    *,
    task_id: str,
    schedule_id: int,
    target: str,
    request,
    source_path: Path,
    output_path: Path,
) -> HostRenderManifest:
    return HostRenderManifest(
        task_id=task_id,
        schedule_id=schedule_id,
        target=target,
        generation_type=request.generation_type,
        title=request.title,
        summary=request.summary,
        prompt=request.prompt,
        source_image_path=str(source_path),
        source_asset_id=request.source_asset_id,
        source_asset_original_file_name=request.source_asset_original_file_name,
        output_path=str(output_path),
        config_json=request.config,
        source_asset_created_at=None,
        task_trace=[],
        handoff_prompt=_build_host_render_prompt(
            task_id=task_id,
            generation_type=request.generation_type,
            title=request.title,
            summary=request.summary,
        ),
    )


async def _prepare_host_render(schedule_id: int, task_id: str | None, target: str) -> HostRenderManifest:
    from app.models.generation_task import GenerationTaskModel
    from app.services.generation.modules import MODULES
    from app.services.generation.pipeline.assets import _pipeline_retrieve_and_select_assets
    from app.services.generation.pipeline.planning import _pipeline_setup_and_planning
    from app.services.generation.pipeline.shared import GenerationPipelineContext, _trace_stage

    init_db()
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        schedule, run_context, notification_presets = _load_schedule_context(db, schedule_id)
        resolved_task_id = task_id or f"cli-s{schedule_id}-{uuid.uuid4().hex[:8]}"

        active_task = (
            db.query(GenerationTaskModel)
            .filter(
                GenerationTaskModel.schedule_id == schedule_id,
                GenerationTaskModel.status.in_(["queued", "running"]),
                GenerationTaskModel.task_id != resolved_task_id,
            )
            .first()
        )
        if active_task:
            raise CLIError(
                f"Schedule {schedule_id} is already being processed by task {active_task.task_id}"
            )

        ensure_task(db, resolved_task_id, status="queued", step="queued", progress=0.0, schedule_id=schedule_id)
        try:
            ctx = GenerationPipelineContext(
                db=db,
                settings=settings,
                task_id=resolved_task_id,
                force=True,
                filters=run_context.filters,
                effects_config=run_context.effects_config,
                schedule_id=schedule_id,
                album_name=schedule.album_name,
                notification_presets=notification_presets,
            )

            module_selection = _pipeline_setup_and_planning(ctx)
            if module_selection is None:
                raise CLIError(f"Unable to prepare host render for schedule {schedule_id}")

            assets_res = await _pipeline_retrieve_and_select_assets(ctx, module_selection)
            if assets_res is None:
                raise CLIError(f"Unable to select assets for schedule {schedule_id}")

            client, page, page_items, photo_selection_trace = assets_res
            module = MODULES.get(module_selection.name)
            if module is None or not hasattr(module, "build_host_render_request"):
                raise CLIError(f"Module {module_selection.name} does not support host rendering")

            host_request = await module.build_host_render_request(
                page_items,
                module_selection.config.get("config", {}),
                client,
                settings,
            )

            source_path, output_path = _host_render_paths(resolved_task_id)
            source_path.write_bytes(host_request.source_image_bytes)

            _trace_stage(
                db,
                resolved_task_id,
                stage="host_render_ready",
                message=f"Prepared host render for {target}",
                step="host_render_ready",
                status="running",
                progress=0.6,
                details={
                    "target": target,
                    "source_asset_id": host_request.source_asset_id,
                    "source_image_path": str(source_path),
                    "output_path": str(output_path),
                    "photo_selection": photo_selection_trace or {},
                },
            )

            upsert_history_entry(
                db,
                resolved_task_id,
                title=host_request.title,
                summary=host_request.summary,
                source_asset_ids=json.dumps([host_request.source_asset_id]),
            )

            host_manifest = _host_render_manifest_from_request(
                task_id=resolved_task_id,
                schedule_id=schedule_id,
                target=target,
                request=host_request,
                source_path=source_path,
                output_path=output_path,
            )
            history_row = _load_history_row(db, resolved_task_id)
            history_config = _parse_json_object(history_row.config_json)
            task_trace = history_config.get("task_trace")

            return HostRenderManifest(
                **{
                    **asdict(host_manifest),
                    "source_asset_created_at": _to_iso_timestamp(
                        getattr(page_items[0], "created_at", None),
                    ),
                    "config_json": {
                        **host_request.config,
                        "photo_selection_trace": photo_selection_trace or {},
                    },
                    "task_trace": list(task_trace) if isinstance(task_trace, list) else [],
                },
            )
        except Exception as exc:
            update_task(db, resolved_task_id, status="failed", step="failed", error=str(exc))
            raise
    finally:
        db.close()


async def _finalize_host_render(manifest_path: Path) -> int:
    from app.services.generation.modules import MODULES
    from app.services.generation.modules.base import GenerationResult
    from app.services.generation.people_context import load_people_context
    from app.services.generation.pipeline.metadata import _build_generation_artifacts
    from app.services.generation.pipeline.notifications import _pipeline_dispatch_notifications
    from app.services.generation.pipeline.persistence import _pipeline_persist_result
    from app.services.generation.pipeline.planning import _resolve_schedule_ai_settings
    from app.services.generation.pipeline.shared import GenerationPipelineContext, _trace_stage

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CLIError("Host manifest is not a JSON object")

    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        raise CLIError("Host manifest did not include task_id")

    schedule_id = payload.get("schedule_id")
    if not isinstance(schedule_id, int):
        raise CLIError("Host manifest did not include schedule_id")

    target = str(payload.get("target") or "").strip()
    if target not in {"agy", "codex"}:
        raise CLIError("Host manifest did not include a valid target")

    output_path = Path(str(payload.get("output_path") or ""))
    if not output_path.exists():
        raise CLIError(f"Host output image not found: {output_path}")

    config_json = payload.get("config_json")
    if not isinstance(config_json, dict):
        config_json = {}

    init_db()
    db = SessionLocal()
    try:
        history_row = _load_history_row(db, task_id)
        original_tags = []
        if history_row.tags_json:
            try:
                parsed_tags = json.loads(history_row.tags_json)
                if isinstance(parsed_tags, list):
                    original_tags = parsed_tags
            except Exception:
                pass
        original_manifest = {
            "title": history_row.title,
            "summary": history_row.summary,
            "tags": original_tags,
        }
        title, summary, tags = _parse_host_metadata(payload, original_manifest)
        config_json = {**config_json, "host_agent_tags": tags, "metadata_source": HOST_METADATA_SOURCE}

        settings = get_or_create_settings(db)
        schedule, _, notification_presets = _load_schedule_context(db, schedule_id)
        _resolve_schedule_ai_settings(db, settings, schedule_id)
        client = build_immich_client(settings)
        module_name = str(payload.get("generation_type") or "").strip()
        module = MODULES.get(module_name)
        if module is None:
            raise CLIError(f"Unknown generation module: {module_name}")

        source_asset_id = str(payload.get("source_asset_id") or "").strip()
        if not source_asset_id:
            raise CLIError("Host manifest did not include source_asset_id")
        source_asset_payload = await client.get_asset_info(source_asset_id)
        source_asset = _asset_summary_to_namespace(
            SimpleNamespace(
                id=source_asset_id,
                original_file_name=source_asset_payload.get("originalFileName"),
                created_at=source_asset_payload.get("fileCreatedAt") or source_asset_payload.get("createdAt"),
            ),
            people=source_asset_payload.get("people") if isinstance(source_asset_payload.get("people"), list) else [],
        )
        people_context = await load_people_context(client, source_asset)

        result = GenerationResult(
            title=title,
            summary=summary,
            image_bytes=output_path.read_bytes(),
            generation_type=module_name,
            provider=target,
            model=target,
            config=config_json,
            source_asset_ids=[source_asset_id],
            output_format="png",
        )

        ctx = GenerationPipelineContext(
            db=db,
            settings=settings,
            task_id=task_id,
            force=True,
            schedule_id=schedule_id,
            album_name=schedule.album_name,
            notification_presets=notification_presets,
        )
        ctx.pipeline_start_time = time.time()
        ctx.task_update(status="running", step="host_finalizing", progress=0.85)
        _trace_stage(
            db,
            task_id,
            stage="host_finalizing",
            message=f"Finalizing host render from {target}",
            step="host_finalizing",
            status="running",
            progress=0.85,
            details={"target": target, "output_path": str(output_path)},
        )

        artifacts = await _build_generation_artifacts(
            db=db,
            client=client,
            source_asset=source_asset,
            people_context=people_context,
            result=result,
            module=module,
            group_name=module_name,
            settings=settings,
            task_id=task_id,
            _task_update=ctx.task_update,
            _progress=ctx.progress_msg,
            photo_selection_trace=(
                config_json.get("photo_selection_trace")
                if isinstance(config_json.get("photo_selection_trace"), dict)
                else None
            ),
        )

        await _pipeline_persist_result(
            ctx=ctx,
            result=result,
            artifacts=artifacts,
            output_path=output_path,
            image_url=f"/api/generation/history/{task_id}/image",
        )
        await _pipeline_dispatch_notifications(ctx, result, f"/api/generation/history/{task_id}/image", artifacts)
        return 0
    finally:
        db.close()


async def _generate(schedule_id: int, task_id: str | None) -> HandoffManifest:
    from app.models.generation_task import GenerationTaskModel

    init_db()
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        schedule, run_context, notification_presets = _load_schedule_context(db, schedule_id)
        client = build_immich_client(settings)
        resolved_task_id = task_id or f"man-{uuid.uuid4().hex[:8]}"

        active_task = (
            db.query(GenerationTaskModel)
            .filter(
                GenerationTaskModel.schedule_id == schedule_id,
                GenerationTaskModel.status.in_(["queued", "running"]),
                GenerationTaskModel.task_id != resolved_task_id,
            )
            .first()
        )
        if active_task:
            raise CLIError(
                f"Schedule {schedule_id} is already being processed by task {active_task.task_id}"
            )

        ensure_task(db, resolved_task_id, status="queued", step="queued", progress=0.0, schedule_id=schedule_id)
        try:
            try:
                await preview_run_now_assets(
                    client=client,
                    filters=run_context.filters,
                    task_id=resolved_task_id,
                    db=db,
                    no_assets_message="No assets matched the filter preset",
                )
            except HTTPException as exc:
                record_run_now_failure_history(
                    db,
                    resolved_task_id,
                    generation_type="schedule_run",
                    title="Failed: schedule run",
                    summary=str(exc.detail) if isinstance(exc.detail, str) else "Failed to preview assets",
                )
                raise CLIError(str(exc.detail) if isinstance(exc.detail, str) else "Failed to preview assets") from exc

            payload_json = run_context.to_run_now_task_payload().to_json()
            update_task(db, resolved_task_id, status="queued", step="queued", progress=0.0, payload_json=payload_json)
            upsert_history_entry(
                db,
                resolved_task_id,
                generation_type="schedule_run",
                status="QUEUED",
                title=f"Queued: {schedule.name}",
                summary="Waiting for the worker to start this scheduled run.",
                source_asset_ids="[]",
                config_json=payload_json,
                task_step="queued",
                schedule_id=schedule_id,
                album_name=schedule.album_name,
            )

            result = await run_generation_cycle(
                db,
                settings,
                resolved_task_id,
                force=True,
                **run_context.to_run_now_task_payload().to_run_generation_kwargs(notification_presets=notification_presets),
            )
            if result is None:
                raise CLIError(f"Generation failed for task {resolved_task_id}")

            row = _load_history_row(db, resolved_task_id)
            if row.status == "FAILED":
                raise CLIError(row.summary or f"Generation failed for task {resolved_task_id}")
            if not row.output_path:
                raise CLIError(f"Generation completed but output path is missing for task {resolved_task_id}")

            return _build_manifest(row)
        except Exception as exc:
            update_task(db, resolved_task_id, status="failed", step="failed", error=str(exc))
            raise
    finally:
        db.close()


def _emit_manifest(manifest: HandoffManifest) -> None:
    json.dump(asdict(manifest), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _emit_host_manifest(manifest: HostRenderManifest) -> None:
    json.dump(asdict(manifest), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args(argv)

    try:
        if args.command == "schedules":
            init_db()
            db = SessionLocal()
            try:
                _list_schedules(db, as_json=args.json)
            finally:
                db.close()
            return 0

        if args.command == "prepare-host":
            manifest = asyncio.run(_prepare_host_render(args.schedule_id, args.task_id, args.target))
            _emit_host_manifest(manifest)
            return 0

        if args.command == "finalize-host":
            return asyncio.run(_finalize_host_render(Path(args.manifest_path)))

        if args.command == "generate":
            manifest = asyncio.run(_generate(args.schedule_id, args.task_id))
            _emit_manifest(manifest)
            return 0

        raise CLIError(f"Unsupported command: {args.command}")
    except CLIError as exc:
        logger.error("%s", exc)
        sys.stderr.write(f"{exc}\n")
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected CLI failure")
        logger.error("%s", exc)
        sys.stderr.write(f"{exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
