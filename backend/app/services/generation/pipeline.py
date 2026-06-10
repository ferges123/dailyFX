from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from app.immich.models import ImmichExifInfo, ImmichSearchFilters
from app.models.settings import SettingsModel
from app.services.generation.ai_budget import AIUsageLimitExceededError
from app.services.generation.ai_vision import analyze_image, analyze_images
from app.services.generation.exif_embedder import embed_exif_metadata
from app.services.generation.history import append_history_trace, history_status_for_task_status, upsert_history_entry
from app.services.generation.people_context import load_people_context
from app.services.generation.tasks import update_task
from app.utils.debug_logger import debug_log, set_debug_mode

logger = logging.getLogger(__name__)

_ALBUM_NAME_SENTINEL = object()

FINAL_AI_VISION_PROMPT = (
    "Analyze this final generated image. Describe what is actually visible in the image itself, "
    "not the source photo used to create it. Return a JSON object with three fields: "
    "'title' (a short, creative 3-5 word title), "
    "'summary' (one concise sentence describing the final image), and "
    "'tags' (a list of 3-6 descriptive keyword strings). "
    "Do not use markdown formatting like ```json, just return the raw JSON object."
)


@dataclass
class GenerationPipelineContext:
    db: Session
    settings: SettingsModel
    task_id: str
    force: bool = False
    filters: ImmichSearchFilters | None = None
    effects_config: dict | None = None
    schedule_id: int | None = None
    album_name: str | None = None
    notification_presets: list | None = None
    webhook_url: str | None = None
    selected_asset_ids: list[str] | None = None
    on_progress: Callable[[str], None] | None = None

    # Internal pipeline state
    source: str = "MANUAL"
    current_step: str = "running"
    current_progress: float = 0.0
    selected_group_name: str = "manual"
    pipeline_start_time: float = 0.0

    def task_update(
        self,
        *,
        status: str | None = None,
        step: str | None = None,
        progress: float | None = None,
        error: str | None = None
    ) -> None:
        if step is not None:
            self.current_step = step
        if progress is not None:
            self.current_progress = progress
        update_task(
            self.db,
            self.task_id,
            status=status or "running",
            step=self.current_step,
            progress=self.current_progress,
            error=error,
        )
        if status != "succeeded":
            history_status = history_status_for_task_status(status) or "RUNNING"
            upsert_history_entry(self.db, self.task_id, status=history_status, task_step=self.current_step)

    def progress_msg(self, msg: str) -> None:
        if self.on_progress:
            self.on_progress(msg)


@dataclass(frozen=True)
class GenerationModuleSelection:
    name: str
    module: object
    config: dict


@dataclass(frozen=True)
class GenerationArtifacts:
    ai_title: str
    ai_summary: str
    ai_tags: list[str]
    ai_token_count: int | None
    ai_provider: str | None
    ai_model: str | None
    exif_info: ImmichExifInfo | None
    metadata_provenance: dict
    final_bytes: bytes
    source_asset: object | None = None


def _build_metadata_provenance() -> dict:
    return {
        "title_source": "module_output",
        "summary_source": "module_output",
        "tags_source": "module_output",
        "people_context": {
            "attempted": False,
            "used": False,
            "names": [],
            "faces": [],
            "prompt_hint": "",
        },
        "source_vision": {
            "attempted": False,
            "succeeded": False,
            "provider": None,
            "model": None,
            "error": None,
        },
        "photo_selection": {
            "attempted": False,
            "succeeded": False,
            "provider": None,
            "model": None,
            "candidate_asset_ids": [],
            "selected_asset_id": None,
            "error": None,
            "fallback_reason": None,
        },
        "final_vision": {
            "attempted": False,
            "succeeded": False,
            "provider": None,
            "model": None,
            "error": None,
        },
        "tag_injections": [],
    }


def _trace_stage(
    db: Session,
    task_id: str,
    *,
    stage: str,
    message: str,
    step: str | None = None,
    status: str | None = None,
    progress: float | None = None,
    details: dict | None = None,
) -> None:
    append_history_trace(
        db,
        task_id,
        stage=stage,
        message=message,
        step=step,
        status=status,
        progress=progress,
        details=details,
    )


def _format_duration(seconds: float | int | None) -> str | None:
    if seconds is None:
        return None
    total_seconds = max(0, int(round(float(seconds))))
    minutes, secs = divmod(total_seconds, 60)
    if minutes and secs:
        return f"{minutes} min {secs} sec"
    if minutes:
        return f"{minutes} min"
    return f"{secs} sec"


def _validate_module_config(module, config: dict) -> None:
    schema = getattr(module, "config_schema", None) or []
    errors: list[str] = []
    for field in schema:
        key = field.get("key")
        value = config.get(key)
        if value is None:
            continue
        field_type = field.get("type")
        if field_type == "number":
            try:
                v = float(value)
            except (TypeError, ValueError):
                errors.append(f"'{key}' must be a number, got {value!r}")
                continue
            if (mn := field.get("min")) is not None and v < mn:
                errors.append(f"'{key}' must be >= {mn}, got {v}")
            if (mx := field.get("max")) is not None and v > mx:
                errors.append(f"'{key}' must be <= {mx}, got {v}")
        elif field_type in ("select", "multiselect"):
            options = {opt["value"] for opt in (field.get("options") or [])}
            if not options:
                continue
            values = value if isinstance(value, list) else [value]
            bad = [v for v in values if v not in options]
            if bad:
                errors.append(f"'{key}' contains invalid value(s): {bad!r}; allowed: {sorted(options)!r}")
    if errors:
        raise ValueError(f"Invalid config for module '{module.name}': {'; '.join(errors)}")


def _is_ai_module(generation_type: str | None, group_name: str | None) -> bool:
    return (generation_type or "").startswith("ai_") or (group_name or "").startswith("ai_")


def _inject_ai_tags(tags: list[str], module, group_name: str) -> list[str]:
    merged = list(tags)
    if "AI" not in merged:
        merged.append("AI")

    label = getattr(module, "label", group_name) or group_name
    style_tag = label[3:] if isinstance(label, str) and label.startswith("AI ") else label
    if style_tag and style_tag not in merged:
        merged.append(style_tag)
    return merged


def _ai_tag_injections(module, group_name: str) -> list[str]:
    label = getattr(module, "label", group_name) or group_name
    style_tag = label[3:] if isinstance(label, str) and label.startswith("AI ") else label
    injections = ["AI"]
    if style_tag:
        injections.append(style_tag)
    return injections


def _resolve_schedule_ai_settings(db: Session, settings: SettingsModel, schedule_id: int | None) -> None:
    try:
        from app.models.schedule import ScheduleModel

        schedule = None
        if schedule_id:
            schedule = db.get(ScheduleModel, schedule_id)
        if not schedule:
            schedule = db.query(ScheduleModel).filter(ScheduleModel.enabled).first()
            if not schedule:
                schedule = db.query(ScheduleModel).first()

        if schedule:
            settings.default_ai_provider = getattr(schedule, "ai_vision_provider", "none")
            settings.default_ai_model = getattr(schedule, "ai_vision_model", "")
            settings.ai_image_provider = getattr(schedule, "ai_image_provider", "none")
            settings.ai_image_model = getattr(schedule, "ai_image_model", "")
            settings.ai_prompt_enrichment = getattr(schedule, "ai_prompt_enrichment", False)
            settings.ai_photo_selection_enabled = getattr(schedule, "ai_photo_selection_enabled", False)
        else:
            settings.default_ai_provider = "none"
            settings.default_ai_model = ""
            settings.ai_image_provider = "none"
            settings.ai_image_model = ""
            settings.ai_prompt_enrichment = False
            settings.ai_photo_selection_enabled = False
    except Exception:
        if not hasattr(settings, "default_ai_provider"):
            settings.default_ai_provider = "none"
        if not hasattr(settings, "default_ai_model"):
            settings.default_ai_model = ""
        if not hasattr(settings, "ai_image_provider"):
            settings.ai_image_provider = "none"
        if not hasattr(settings, "ai_image_model"):
            settings.ai_image_model = ""
        if not hasattr(settings, "ai_prompt_enrichment"):
            settings.ai_prompt_enrichment = False
        if not hasattr(settings, "ai_photo_selection_enabled"):
            settings.ai_photo_selection_enabled = False


def _select_generation_module(effects_config: dict) -> GenerationModuleSelection | None:
    from app.services.generation import engine as engine_module

    groups_config = _merge_module_defaults(effects_config)
    modules = getattr(engine_module, "MODULES", {}) or {}
    active_groups = []
    for name, data in groups_config.items():
        if data.get("enabled", False):
            mod = modules.get(name)
            if mod is not None and getattr(mod, "enabled", True):
                active_groups.append((name, data))
    debug_log(
        "Active modules",
        active=[f"{n}(w={d['weight']})" for n, d in active_groups],
        total_in_preset=len(effects_config),
    )
    if not active_groups:
        return None

    weights = [data.get("weight", 1) for _, data in active_groups]
    group_name, group_config = engine_module.random.choices(active_groups, weights=weights, k=1)[0]
    module = modules.get(group_name)
    if module is None:
        raise ValueError(f"Unknown generation group: {group_name}")
    return GenerationModuleSelection(name=group_name, module=module, config=group_config)


async def _search_assets_for_generation(
    *,
    settings: SettingsModel,
    filters: ImmichSearchFilters,
    task_id: str,
    _task_update: Callable[..., None],
    _progress: Callable[[str], None],
) -> tuple[object, object]:
    from app.services.generation import engine as engine_module

    client = engine_module.build_immich_client(settings)
    debug_log(
        "Searching assets",
        task_id=task_id,
        album_ids=filters.album_ids,
        media_type=filters.media_type,
        person_filters=[f"{p.person_id}({p.mode})" for p in (filters.person_filters or [])],
    )
    _task_update(step="selecting_asset", progress=0.1)
    _progress("Searching for photos…")
    page = await client.search_assets(filters)
    return client, page


def _search_filters_for_module(*, filters: ImmichSearchFilters, module, settings: SettingsModel) -> ImmichSearchFilters:
    source_asset_count = max(1, int(getattr(module, "source_asset_count", 1) or 1))
    ai_photo_selection_enabled = bool(getattr(settings, "ai_photo_selection_enabled", False))
    random_size = 4 if source_asset_count > 1 or ai_photo_selection_enabled else 1
    return replace(filters, random_size=random_size)


def _select_page_items(
    *,
    page,
    selected_asset_ids: list[str] | None,
    task_id: str,
    _task_update: Callable[..., None],
) -> list:
    page_items = page.items
    if selected_asset_ids:
        selected_id_set = {
            asset_id for asset_id in selected_asset_ids if isinstance(asset_id, str) and asset_id.strip()
        }
        if selected_id_set:
            filtered_items = [item for item in page.items if item.id in selected_id_set]
            if filtered_items:
                debug_log(
                    "Filtered to selected assets",
                    task_id=task_id,
                    selected=list(selected_id_set),
                    matched=len(filtered_items),
                )
                return filtered_items
            debug_log(
                "Skipping: selected assets not in search results", task_id=task_id, selected=list(selected_id_set)
            )
            logger.warning("No selected assets matched the current search results.")
            _task_update(status="failed", step="failed", error="No selected assets matched the current search results")
            return []
    return page_items


def _dedupe_page_items(items: list) -> list:
    unique_items = []
    seen_ids = set()
    for item in items:
        asset_id = getattr(item, "id", None)
        if not asset_id or asset_id in seen_ids:
            continue
        unique_items.append(item)
        seen_ids.add(asset_id)
    return unique_items


def _prepare_page_items_for_module(
    *,
    page,
    module,
    selected_asset_ids: list[str] | None,
    ai_photo_selection_enabled: bool,
    task_id: str,
    _task_update: Callable[..., None],
) -> list | None:
    page_items = _select_page_items(
        page=page, selected_asset_ids=selected_asset_ids, task_id=task_id, _task_update=_task_update
    )
    if not page_items:
        return None

    unique_items = _dedupe_page_items(page_items)
    if not unique_items:
        return None

    source_asset_count = max(1, int(getattr(module, "source_asset_count", 1) or 1))
    if source_asset_count > 1:
        return unique_items[:source_asset_count]
    if ai_photo_selection_enabled:
        return unique_items[:4]
    return page_items


def _parse_ranking_payload(result) -> dict:
    candidates = [getattr(result, "summary", None), getattr(result, "title", None)]
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        text = candidate.strip().replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(text)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


async def rank_source_assets_for_effect(
    *,
    client,
    settings: SettingsModel,
    candidates: list,
    module,
    task_id: str,
    trace: dict,
):
    candidate_asset_ids = [getattr(asset, "id", None) for asset in candidates if getattr(asset, "id", None)]
    trace.update(
        attempted=True,
        succeeded=False,
        provider=getattr(settings, "default_ai_provider", None),
        model=getattr(settings, "default_ai_model", None),
        candidate_asset_ids=candidate_asset_ids,
        selected_asset_id=candidate_asset_ids[0] if candidate_asset_ids else None,
        error=None,
        fallback_reason=None,
        selection_reason=None,
    )
    if not candidates:
        trace.update(error="No candidates available", fallback_reason="no_candidates")
        return None

    try:
        effect_label = getattr(module, "label", getattr(module, "name", "selected effect"))
        effect_description = getattr(module, "description", "")
        total = min(4, len(candidates))
        candidate_images = [await client.get_asset_data(asset.id) for asset in candidates[:4]]
        prompt = (
            "Compare these candidate source photos for a DailyFX effect. "
            f"Effect/filter to apply: {effect_label}. Description: {effect_description}. "
            f"There are {total} candidates, shown in order as Candidate 1 through Candidate {total}. "
            "Choose which candidate will produce the best final result after applying this effect. "
            "Consider composition, subject clarity, lighting, colors, and how well the selected filter/effect will work. "
            "Return raw JSON only: selected_index (1-based), selected_asset_id if known, and "
            "selection_reason: one short sentence explaining why it beats the other candidates."
        )
        result = await analyze_images(
            settings,
            candidate_images,
            provider=getattr(settings, "default_ai_provider", None),
            model=getattr(settings, "default_ai_model", None),
            prompt=prompt,
        )
        parsed = _parse_ranking_payload(result)
        selected_index = parsed.get("selected_index") or parsed.get("index")
        if not isinstance(selected_index, int) or not 1 <= selected_index <= len(candidates[:4]):
            selected_index = 1
            trace["fallback_reason"] = "invalid_ranking_response"
        selected = candidates[selected_index - 1]
        selection_reason = parsed.get("selection_reason") or parsed.get("reason")
        selection_reason = selection_reason if isinstance(selection_reason, str) else None
        trace.update(
            succeeded=True,
            selected_asset_id=selected.id,
            selection_reason=selection_reason,
        )
        debug_log(
            "AI photo selection selected asset",
            task_id=task_id,
            selected_asset_id=selected.id,
            candidate_asset_ids=candidate_asset_ids,
            selection_reason=selection_reason,
        )
        return selected
    except Exception as exc:
        fallback = candidates[0]
        trace.update(
            succeeded=False,
            selected_asset_id=getattr(fallback, "id", None),
            error=str(exc),
            fallback_reason="ranking_failed",
        )
        debug_log("AI photo selection failed, using first candidate", task_id=task_id, error=str(exc))
        logger.warning("AI photo selection failed for %s, using first candidate: %s", task_id, exc)
        return fallback


def _initial_artifact_state(result) -> dict[str, object]:
    return {
        "ai_title": result.title,
        "ai_summary": result.summary,
        "ai_tags": [],
        "ai_token_count": None,
        "ai_provider": result.provider,
        "ai_model": result.model,
        "exif_info": None,
        "source_asset": None,
    }


def _select_generation_page_items(
    *,
    page,
    selected_asset_ids: list[str] | None,
    task_id: str,
    _task_update: Callable[..., None],
) -> list | None:
    page_items = _select_page_items(
        page=page, selected_asset_ids=selected_asset_ids, task_id=task_id, _task_update=_task_update
    )
    if not page_items:
        return None
    return page_items


async def _resolve_generation_source_context(
    *,
    page,
    result,
    client,
    task_id: str,
) -> tuple[object | None, object | None]:
    source_asset = None
    people_context = None
    source_asset_id = result.source_asset_ids[0] if result.source_asset_ids else None
    if source_asset_id:
        source_asset = next((a for a in page.items if a.id == source_asset_id), None)
        debug_log(
            "Source asset",
            task_id=task_id,
            asset_id=source_asset_id,
            filename=getattr(source_asset, "original_file_name", None),
            created_at=getattr(source_asset, "created_at", None),
        )
        people_context = await load_people_context(client, source_asset) if source_asset is not None else None
    return source_asset, people_context


def _generation_output_paths(task_id: str) -> tuple[object, str]:
    from app.services.generation import engine as engine_module

    output_dir = engine_module.get_settings().data_dir / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{task_id}.png"
    image_url = f"/api/generation/history/{task_id}/image"
    return output_path, image_url


async def _run_selected_module(
    *,
    db: Session,
    module,
    group_name: str,
    group_config: dict,
    page_items: list,
    client,
    settings: SettingsModel,
    task_id: str,
    _task_update: Callable[..., None],
    _progress: Callable[[str], None],
):
    _validate_module_config(module, group_config.get("config", {}))
    _task_update(step="applying_effect", progress=0.25)
    _progress(f"Applying effect: {module.label}…")

    debug_log(
        "Starting module execution",
        task_id=task_id,
        module=group_name,
        config=group_config.get("config", {}),
        assets_count=len(page_items),
    )
    start_time = time.time()
    result = await module.run(page_items, group_config.get("config", {}), client, settings)
    elapsed = time.time() - start_time
    debug_log(
        "Module execution completed",
        task_id=task_id,
        module=group_name,
        elapsed_seconds=f"{elapsed:.2f}",
        result_size=len(result.image_bytes) if result.image_bytes else 0,
        source_asset_ids=result.source_asset_ids,
        title=result.title,
    )
    _trace_stage(
        db,
        task_id,
        stage="module_complete",
        message=f"Module {group_name} completed in {elapsed:.2f}s",
        step="applying_effect",
        status="running",
        progress=0.25,
        details={"elapsed_seconds": round(elapsed, 2), "generation_type": result.generation_type},
    )
    return result


async def _persist_generation_outputs(
    *,
    db: Session,
    task_id: str,
    result,
    artifacts: GenerationArtifacts,
    output_path,
    image_url: str,
    schedule_id: int | None,
    album_name: str | None,
    notification_presets: list,
    webhook_url: str | None,
    pipeline_start_time: float,
    _task_update: Callable[..., None],
    _progress: Callable[[str], None],
) -> dict:
    from app.services.generation import engine as engine_module

    _task_update(step="saving_result", progress=0.95)
    _progress("Saving result…")
    _trace_stage(
        db,
        task_id,
        stage="saving_result",
        message="Saving result and writing history entry",
        step="saving_result",
        status="running",
        progress=0.95,
    )
    engine_module._persist_generation_result(
        db=db,
        task_id=task_id,
        result=result,
        artifacts=artifacts,
        output_path=output_path,
        image_url=image_url,
        schedule_id=schedule_id,
        album_name=album_name,
    )
    debug_log(
        "History entry saved",
        task_id=task_id,
        status="PENDING_REVIEW",
        generation_type=result.generation_type,
        album_name=album_name,
        ai_title=artifacts.ai_title,
        tags_count=len(artifacts.ai_tags),
    )

    _task_update(status="succeeded", step="succeeded", progress=1.0, error=None)
    total_elapsed = max(0.0, time.time() - pipeline_start_time)
    duration_label = _format_duration(total_elapsed)
    _trace_stage(
        db,
        task_id,
        stage="completed",
        message=f"Generation completed successfully in {duration_label}"
        if duration_label
        else "Generation completed successfully",
        step="succeeded",
        status="succeeded",
        progress=1.0,
        details={"elapsed_seconds": round(total_elapsed, 2), "generation_type": result.generation_type},
    )
    await engine_module._dispatch_generation_outputs(
        notification_presets=notification_presets,
        webhook_url=webhook_url,
        result=result,
        task_id=task_id,
        image_url=image_url,
        title=artifacts.ai_title,
        summary=artifacts.ai_summary,
    )
    debug_log("Generation cycle completed", task_id=task_id)
    return {"task_id": task_id, "type": result.generation_type, **result.config}


async def _apply_source_vision(
    *,
    db: Session,
    client,
    source_asset,
    source_asset_id: str,
    people_context,
    settings: SettingsModel,
    task_id: str,
    state: dict[str, object],
    metadata_provenance: dict,
    _task_update: Callable[..., None],
    _progress: Callable[[str], None],
) -> None:
    from app.services.generation import engine as engine_module

    metadata_provenance["source_vision"]["attempted"] = True
    _trace_stage(
        db,
        task_id,
        stage="source_vision",
        message="Analyzing source image with AI",
        step="analyzing_image",
        status="running",
        progress=0.55,
    )
    _task_update(step="analyzing_image", progress=0.55)
    _progress("Analyzing image with AI…")
    debug_log(
        "Starting AI vision analysis",
        task_id=task_id,
        provider=settings.default_ai_provider,
        model=settings.default_ai_model,
    )
    t0 = time.time()
    original_bytes = await client.get_asset_data(source_asset_id)
    ai_analysis = await engine_module.analyze_image(
        settings,
        original_bytes,
        context_hint=people_context.anonymized_prompt_hint() if people_context else None,
    )
    state["ai_title"] = ai_analysis.title
    state["ai_summary"] = ai_analysis.summary
    state["ai_tags"] = ai_analysis.tags or []
    state["ai_token_count"] = ai_analysis.token_count
    state["ai_provider"] = state["ai_provider"] or ai_analysis.provider
    state["ai_model"] = state["ai_model"] or ai_analysis.model
    metadata_provenance["source_vision"].update(
        succeeded=True,
        provider=ai_analysis.provider,
        model=ai_analysis.model,
        people_context_used=bool(people_context),
    )
    metadata_provenance["title_source"] = "source_vision"
    metadata_provenance["summary_source"] = "source_vision"
    metadata_provenance["tags_source"] = "source_vision"
    debug_log(
        "AI vision completed",
        task_id=task_id,
        elapsed_seconds=f"{time.time() - t0:.2f}",
        title=state["ai_title"],
        tags=state["ai_tags"],
        tokens=state["ai_token_count"],
        provider=state["ai_provider"],
        model=state["ai_model"],
    )


async def _apply_final_vision(
    *,
    db: Session,
    result,
    group_name: str,
    settings: SettingsModel,
    task_id: str,
    state: dict[str, object],
    metadata_provenance: dict,
    _task_update: Callable[..., None],
    _progress: Callable[[str], None],
) -> None:
    from app.services.generation import engine as engine_module

    metadata_provenance["final_vision"]["attempted"] = True
    _trace_stage(
        db,
        task_id,
        stage="final_vision",
        message="Analyzing final generated image with AI",
        step="analyzing_final_image",
        status="running",
        progress=0.7,
    )
    _task_update(step="analyzing_final_image", progress=0.7)
    _progress("Analyzing final image with AI…")
    debug_log(
        "Starting final AI vision analysis",
        task_id=task_id,
        provider=settings.default_ai_provider,
        model=settings.default_ai_model,
    )
    t1 = time.time()
    final_ai_analysis = await engine_module.analyze_image(settings, result.image_bytes, prompt=FINAL_AI_VISION_PROMPT)
    state["ai_title"] = final_ai_analysis.title
    state["ai_summary"] = final_ai_analysis.summary
    state["ai_tags"] = final_ai_analysis.tags or []
    state["ai_token_count"] = final_ai_analysis.token_count
    state["ai_provider"] = state["ai_provider"] or final_ai_analysis.provider
    state["ai_model"] = state["ai_model"] or final_ai_analysis.model
    metadata_provenance["final_vision"].update(
        succeeded=True,
        provider=final_ai_analysis.provider,
        model=final_ai_analysis.model,
    )
    metadata_provenance["title_source"] = "final_vision"
    metadata_provenance["summary_source"] = "final_vision"
    metadata_provenance["tags_source"] = "final_vision"
    debug_log(
        "Final AI vision completed",
        task_id=task_id,
        elapsed_seconds=f"{time.time() - t1:.2f}",
        title=state["ai_title"],
        tags=state["ai_tags"],
        tokens=state["ai_token_count"],
        provider=state["ai_provider"],
        model=state["ai_model"],
    )


async def _build_generation_artifacts(
    *,
    db: Session,
    client,
    source_asset,
    people_context,
    result,
    module,
    group_name: str,
    settings: SettingsModel,
    task_id: str,
    _task_update: Callable[..., None],
    _progress: Callable[[str], None],
    photo_selection_trace: dict | None = None,
) -> GenerationArtifacts:
    state = _initial_artifact_state(result)
    metadata_provenance = _build_metadata_provenance()
    if photo_selection_trace:
        metadata_provenance["photo_selection"].update(photo_selection_trace)

    source_asset_id = getattr(source_asset, "id", None) if source_asset is not None else None
    if source_asset_id:
        if people_context:
            metadata_provenance["people_context"] = {
                "attempted": True,
                "used": True,
                **people_context.to_dict(),
            }
        elif isinstance(getattr(source_asset, "people", None), list) and getattr(source_asset, "people", None):
            metadata_provenance["people_context"]["attempted"] = True

        prompt_enrichment_context = (
            result.config.get("prompt_enrichment_context") if isinstance(result.config, dict) else None
        )
        if isinstance(prompt_enrichment_context, dict) and prompt_enrichment_context.get("context_hint"):
            metadata_provenance["prompt_enrichment_context"] = prompt_enrichment_context
            _trace_stage(
                db,
                task_id,
                stage="prompt_enrichment_context",
                message="AI prompt enrichment context assembled",
                step="analyzing_image",
                status="running",
                progress=0.54,
                details=prompt_enrichment_context,
            )
            debug_log(
                "Prompt enrichment context stored in history",
                task_id=task_id,
                album_name=prompt_enrichment_context.get("album_name"),
                people_names=prompt_enrichment_context.get("people_names"),
                exif_summary=prompt_enrichment_context.get("exif_summary"),
            )

        if settings.default_ai_provider != "none":
            try:
                await _apply_source_vision(
                    db=db,
                    client=client,
                    source_asset=source_asset,
                    source_asset_id=source_asset_id,
                    people_context=people_context,
                    settings=settings,
                    task_id=task_id,
                    state=state,
                    metadata_provenance=metadata_provenance,
                    _task_update=_task_update,
                    _progress=_progress,
                )
            except Exception as ai_exc:
                metadata_provenance["source_vision"].update(succeeded=False, error=str(ai_exc))
                _trace_stage(
                    db,
                    task_id,
                    stage="source_vision_failed",
                    message=str(ai_exc),
                    step="analyzing_image",
                    status="running",
                    progress=0.55,
                    details={"provider": settings.default_ai_provider, "model": settings.default_ai_model},
                )
                debug_log("AI vision failed, using module defaults", task_id=task_id, error=str(ai_exc))
                logger.warning("AI analysis failed, falling back to module defaults: %s", ai_exc)

        if _is_ai_module(result.generation_type, group_name) and settings.default_ai_provider != "none":
            try:
                await _apply_final_vision(
                    db=db,
                    result=result,
                    group_name=group_name,
                    settings=settings,
                    task_id=task_id,
                    state=state,
                    metadata_provenance=metadata_provenance,
                    _task_update=_task_update,
                    _progress=_progress,
                )
            except Exception as ai_exc:
                metadata_provenance["final_vision"].update(succeeded=False, error=str(ai_exc))
                _trace_stage(
                    db,
                    task_id,
                    stage="final_vision_failed",
                    message=str(ai_exc),
                    step="analyzing_final_image",
                    status="running",
                    progress=0.7,
                    details={"provider": settings.default_ai_provider, "model": settings.default_ai_model},
                )
                debug_log("Final AI vision failed, keeping earlier metadata", task_id=task_id, error=str(ai_exc))
                logger.warning("Final AI vision failed, keeping earlier metadata: %s", ai_exc)

        if _is_ai_module(result.generation_type, group_name):
            state["ai_tags"] = _inject_ai_tags(state["ai_tags"], module, group_name)
            metadata_provenance["tag_injections"] = _ai_tag_injections(module, group_name)

        debug_log("Fetching EXIF data", task_id=task_id, asset_id=source_asset_id)
        _task_update(step="embedding_metadata", progress=0.8)
        _trace_stage(
            db,
            task_id,
            stage="exif",
            message="Embedding EXIF metadata",
            step="embedding_metadata",
            status="running",
            progress=0.8,
        )
        state["exif_info"] = await client.get_asset_exif(source_asset_id)
        debug_log(
            "EXIF data received",
            task_id=task_id,
            make=state["exif_info"].get("make"),
            model=state["exif_info"].get("model"),
            lat=state["exif_info"].get("latitude"),
            lon=state["exif_info"].get("longitude"),
            taken=state["exif_info"].get("dateTimeOriginal"),
        )
        _progress("Embedding metadata…")
        final_bytes = embed_exif_metadata(result.image_bytes, source_asset, state["ai_title"], state["exif_info"])
    else:
        debug_log("No source asset — skipping EXIF embed", task_id=task_id)
        _trace_stage(
            db,
            task_id,
            stage="exif_skipped",
            message="No source asset, skipping EXIF embedding",
            step="embedding_metadata",
            status="running",
            progress=0.8,
        )
        final_bytes = result.image_bytes

    return GenerationArtifacts(
        ai_title=state["ai_title"],
        ai_summary=state["ai_summary"],
        ai_tags=state["ai_tags"],
        ai_token_count=state["ai_token_count"],
        ai_provider=state["ai_provider"],
        ai_model=state["ai_model"],
        exif_info=state["exif_info"],
        metadata_provenance=metadata_provenance,
        final_bytes=final_bytes,
        source_asset=source_asset,
    )


def _pipeline_setup_and_planning(ctx: GenerationPipelineContext) -> GenerationModuleSelection | None:
    ctx.source = "MANUAL" if ctx.force else "AUTOMATION"
    logger.info(f"🔵 run_generation_cycle START - task_id={ctx.task_id}, source={ctx.source}")
    ctx.pipeline_start_time = time.time()

    _resolve_schedule_ai_settings(ctx.db, ctx.settings, ctx.schedule_id)
    set_debug_mode(ctx.settings.debug_mode)

    ctx.selected_group_name = ctx.source.lower()
    ctx.task_update(status="running", step="running", progress=0.0)

    upsert_history_entry(
        ctx.db,
        ctx.task_id,
        generation_type=ctx.selected_group_name,
        status="RUNNING",
        title=f"{ctx.source.title()} generation running",
        summary="Generation is in progress",
        source_asset_ids="[]",
        config_json=json.dumps({"state": "running"}),
        task_step=ctx.current_step,
        schedule_id=ctx.schedule_id,
        album_name=ctx.album_name,
    )
    _trace_stage(
        ctx.db, ctx.task_id, stage="start", message="Generation started", step="running", status="running", progress=0.0
    )
    debug_log(
        "Generation cycle started",
        task_id=ctx.task_id,
        source=ctx.source,
        schedule_id=ctx.schedule_id,
        album_name=ctx.album_name,
        ai_provider=ctx.settings.default_ai_provider,
        ai_model=ctx.settings.default_ai_model,
        ai_image_provider=ctx.settings.ai_image_provider,
        ai_image_model=ctx.settings.ai_image_model,
        debug_mode=ctx.settings.debug_mode,
    )

    if ctx.effects_config is None:
        debug_log("Skipping: no effects_config provided", task_id=ctx.task_id)
        logger.warning("No effects_config provided, skipping.")
        ctx.task_update(status="failed", step="failed", error="No effects_config provided")
        return None

    try:
        module_selection = _select_generation_module(ctx.effects_config)
    except ValueError as exc:
        debug_log("ERROR: unknown module", task_id=ctx.task_id, module=str(exc))
        logger.error("%s", exc)
        ctx.task_update(status="failed", step="failed", error=str(exc))
        return None

    if module_selection is None:
        debug_log("Skipping: no active modules", task_id=ctx.task_id)
        logger.info("No active modification groups, skipping.")
        ctx.task_update(status="failed", step="failed", error="No active modification groups")
        return None

    ctx.selected_group_name = module_selection.name
    debug_log("Module selected", task_id=ctx.task_id, module=ctx.selected_group_name, config=module_selection.config.get("config", {}))
    logger.info(f"🎯 Selected generation group: {ctx.selected_group_name} (task_id={ctx.task_id})")
    _trace_stage(
        ctx.db,
        ctx.task_id,
        stage="module_selected",
        message=f"Selected generation group {ctx.selected_group_name}",
        step=ctx.current_step,
        status="running",
        progress=ctx.current_progress,
        details={"group": ctx.selected_group_name, "label": getattr(module_selection.module, "label", ctx.selected_group_name)},
    )
    return module_selection


async def _pipeline_retrieve_and_select_assets(
    ctx: GenerationPipelineContext,
    module_selection: GenerationModuleSelection,
) -> tuple[object, list[object], dict | None] | None:
    if ctx.filters is None:
        debug_log("Skipping: no filters provided", task_id=ctx.task_id)
        logger.warning("No filters provided, skipping.")
        ctx.task_update(status="failed", step="failed", error="No filters provided")
        return None

    client, page = await _search_assets_for_generation(
        settings=ctx.settings,
        filters=_search_filters_for_module(filters=ctx.filters, module=module_selection.module, settings=ctx.settings),
        task_id=ctx.task_id,
        _task_update=ctx.task_update,
        _progress=ctx.progress_msg,
    )
    _trace_stage(
        ctx.db,
        ctx.task_id,
        stage="assets_found",
        message=f"Found {len(page.items)} candidate assets",
        step=ctx.current_step,
        status="running",
        progress=ctx.current_progress,
        details={"asset_count": len(page.items)},
    )
    if not page.items:
        debug_log("Skipping: no assets found", task_id=ctx.task_id)
        logger.warning("No assets found for the given automation filter.")
        ctx.task_update(status="failed", step="failed", error="No assets found for the given automation filter")
        return None

    debug_log(
        "Random asset selected", task_id=ctx.task_id, count=len(page.items), asset_ids=[a.id for a in page.items[:10]]
    )
    logger.info(f"📸 Selected random asset, running module {ctx.selected_group_name} (task_id={ctx.task_id})")

    ai_photo_selection_enabled = bool(getattr(ctx.settings, "ai_photo_selection_enabled", False)) and int(
        getattr(module_selection.module, "source_asset_count", 1) or 1
    ) == 1
    page_items = _prepare_page_items_for_module(
        page=page,
        module=module_selection.module,
        selected_asset_ids=ctx.selected_asset_ids,
        ai_photo_selection_enabled=ai_photo_selection_enabled,
        task_id=ctx.task_id,
        _task_update=ctx.task_update,
    )
    if not page_items:
        return None

    photo_selection_trace = None
    if ai_photo_selection_enabled:
        photo_selection_trace = {}
        selected_asset = await rank_source_assets_for_effect(
            client=client,
            settings=ctx.settings,
            candidates=page_items,
            module=module_selection.module,
            task_id=ctx.task_id,
            trace=photo_selection_trace,
        )
        if selected_asset is not None:
            page_items = [selected_asset]
        _trace_stage(
            ctx.db,
            ctx.task_id,
            stage="photo_selection",
            message="AI photo selection completed"
            if photo_selection_trace.get("succeeded")
            else "AI photo selection fell back to the first candidate",
            step=ctx.current_step,
            status="running",
            progress=ctx.current_progress,
            details=photo_selection_trace,
        )
    _trace_stage(
        ctx.db,
        ctx.task_id,
        stage="assets_selected",
        message=f"Selected {len(page_items)} asset(s) for generation",
        step=ctx.current_step,
        status="running",
        progress=ctx.current_progress,
        details={"selected_asset_ids": [a.id for a in page_items]},
    )
    return client, page_items, photo_selection_trace


async def _pipeline_execute_module(
    ctx: GenerationPipelineContext,
    module_selection: GenerationModuleSelection,
    page_items: list[object],
    client: object,
) -> object:
    original_album_name = getattr(ctx.settings, "_generation_album_name", _ALBUM_NAME_SENTINEL)
    if ctx.album_name is not None:
        ctx.settings._generation_album_name = ctx.album_name
    elif hasattr(ctx.settings, "_generation_album_name"):
        delattr(ctx.settings, "_generation_album_name")

    try:
        result = await _run_selected_module(
            db=ctx.db,
            module=module_selection.module,
            group_name=module_selection.name,
            group_config=module_selection.config,
            page_items=page_items,
            client=client,
            settings=ctx.settings,
            task_id=ctx.task_id,
            _task_update=ctx.task_update,
            _progress=ctx.progress_msg,
        )
        return result
    finally:
        if original_album_name is _ALBUM_NAME_SENTINEL:
            if hasattr(ctx.settings, "_generation_album_name"):
                delattr(ctx.settings, "_generation_album_name")
        else:
            ctx.settings._generation_album_name = original_album_name


async def _pipeline_enrich_metadata(
    ctx: GenerationPipelineContext,
    module_selection: GenerationModuleSelection,
    result: object,
    page: object,
    client: object,
    photo_selection_trace: dict | None,
) -> tuple[object, GenerationArtifacts]:
    source_asset, people_context = await _resolve_generation_source_context(
        page=page,
        result=result,
        client=client,
        task_id=ctx.task_id,
    )

    artifacts = await _build_generation_artifacts(
        db=ctx.db,
        client=client,
        source_asset=source_asset,
        people_context=people_context,
        result=result,
        module=module_selection.module,
        group_name=module_selection.name,
        settings=ctx.settings,
        task_id=ctx.task_id,
        _task_update=ctx.task_update,
        _progress=ctx.progress_msg,
        photo_selection_trace=photo_selection_trace,
    )
    return source_asset, artifacts


async def run_generation_pipeline(
    db: Session,
    settings: SettingsModel,
    task_id: str,
    force: bool = False,
    filters: ImmichSearchFilters | None = None,
    effects_config: dict | None = None,
    schedule_id: int | None = None,
    album_name: str | None = None,
    notification_presets: list = None,
    webhook_url: str | None = None,
    selected_asset_ids: list[str] | None = None,
    on_progress: "Callable[[str], None] | None" = None,
) -> dict | None:
    source = "MANUAL" if force else "AUTOMATION"
    logger.info(f"🔵 run_generation_cycle START - task_id={task_id}, source={source}")
    pipeline_start_time = time.time()

    _resolve_schedule_ai_settings(db, settings, schedule_id)
    set_debug_mode(settings.debug_mode)

    current_step = "running"
    current_progress = 0.0
    selected_group_name = source.lower()

    def _task_update(
        *, status: str | None = None, step: str | None = None, progress: float | None = None, error: str | None = None
    ) -> None:
        nonlocal current_step, current_progress
        if step is not None:
            current_step = step
        if progress is not None:
            current_progress = progress
        update_task(
            db,
            task_id,
            status=status or "running",
            step=current_step,
            progress=current_progress,
            error=error,
        )
        if status != "succeeded":
            history_status = history_status_for_task_status(status) or "RUNNING"
            upsert_history_entry(db, task_id, status=history_status, task_step=current_step)

    _task_update(status="running", step="running", progress=0.0)
    upsert_history_entry(
        db,
        task_id,
        generation_type=selected_group_name,
        status="RUNNING",
        title=f"{source.title()} generation running",
        summary="Generation is in progress",
        source_asset_ids="[]",
        config_json=json.dumps({"state": "running"}),
        task_step=current_step,
        schedule_id=schedule_id,
        album_name=album_name,
    )
    _trace_stage(
        db, task_id, stage="start", message="Generation started", step="running", status="running", progress=0.0
    )
    debug_log(
        "Generation cycle started",
        task_id=task_id,
        source=source,
        schedule_id=schedule_id,
        album_name=album_name,
        ai_provider=settings.default_ai_provider,
        ai_model=settings.default_ai_model,
        ai_image_provider=settings.ai_image_provider,
        ai_image_model=settings.ai_image_model,
        debug_mode=settings.debug_mode,
    )

    def _progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    if effects_config is None:
        debug_log("Skipping: no effects_config provided", task_id=task_id)
        logger.warning("No effects_config provided, skipping.")
        _task_update(status="failed", step="failed", error="No effects_config provided")
        return None

    try:
        module_selection = _select_generation_module(effects_config)
    except ValueError as exc:
        debug_log("ERROR: unknown module", task_id=task_id, module=str(exc))
        logger.error("%s", exc)
        _task_update(status="failed", step="failed", error=str(exc))
        return None
    if module_selection is None:
        debug_log("Skipping: no active modules", task_id=task_id)
        logger.info("No active modification groups, skipping.")
        _task_update(status="failed", step="failed", error="No active modification groups")
        return None

    selected_group_name = module_selection.name
    module = module_selection.module
    group_config = module_selection.config
    debug_log("Module selected", task_id=task_id, module=selected_group_name, config=group_config.get("config", {}))
    logger.info(f"🎯 Selected generation group: {selected_group_name} (task_id={task_id})")
    _trace_stage(
        db,
        task_id,
        stage="module_selected",
        message=f"Selected generation group {selected_group_name}",
        step=current_step,
        status="running",
        progress=current_progress,
        details={"group": selected_group_name, "label": getattr(module, "label", selected_group_name)},
    )

    if filters is None:
        debug_log("Skipping: no filters provided", task_id=task_id)
        logger.warning("No filters provided, skipping.")
        _task_update(status="failed", step="failed", error="No filters provided")
        return None

    client, page = await _search_assets_for_generation(
        settings=settings,
        filters=_search_filters_for_module(filters=filters, module=module, settings=settings),
        task_id=task_id,
        _task_update=_task_update,
        _progress=_progress,
    )
    _trace_stage(
        db,
        task_id,
        stage="assets_found",
        message=f"Found {len(page.items)} candidate assets",
        step=current_step,
        status="running",
        progress=current_progress,
        details={"asset_count": len(page.items)},
    )
    if not page.items:
        debug_log("Skipping: no assets found", task_id=task_id)
        logger.warning("No assets found for the given automation filter.")
        _task_update(status="failed", step="failed", error="No assets found for the given automation filter")
        return None

    debug_log(
        "Random asset selected", task_id=task_id, count=len(page.items), asset_ids=[a.id for a in page.items[:10]]
    )
    logger.info(f"📸 Selected random asset, running module {selected_group_name} (task_id={task_id})")

    ai_photo_selection_enabled = bool(getattr(settings, "ai_photo_selection_enabled", False)) and int(
        getattr(module, "source_asset_count", 1) or 1
    ) == 1
    page_items = _prepare_page_items_for_module(
        page=page,
        module=module,
        selected_asset_ids=selected_asset_ids,
        ai_photo_selection_enabled=ai_photo_selection_enabled,
        task_id=task_id,
        _task_update=_task_update,
    )
    if not page_items:
        return None
    photo_selection_trace = None
    if ai_photo_selection_enabled:
        photo_selection_trace = {}
        selected_asset = await rank_source_assets_for_effect(
            client=client,
            settings=settings,
            candidates=page_items,
            module=module,
            task_id=task_id,
            trace=photo_selection_trace,
        )
        if selected_asset is not None:
            page_items = [selected_asset]
        _trace_stage(
            db,
            task_id,
            stage="photo_selection",
            message="AI photo selection completed"
            if photo_selection_trace.get("succeeded")
            else "AI photo selection fell back to the first candidate",
            step=current_step,
            status="running",
            progress=current_progress,
            details=photo_selection_trace,
        )
    _trace_stage(
        db,
        task_id,
        stage="assets_selected",
        message=f"Selected {len(page_items)} asset(s) for generation",
        step=current_step,
        status="running",
        progress=current_progress,
        details={"selected_asset_ids": [a.id for a in page_items]},
    )

    output_path, image_url = _generation_output_paths(task_id)

    original_album_name = getattr(settings, "_generation_album_name", _ALBUM_NAME_SENTINEL)
    if album_name is not None:
        settings._generation_album_name = album_name
    elif hasattr(settings, "_generation_album_name"):
        delattr(settings, "_generation_album_name")

    try:
        try:
            result = await _run_selected_module(
                db=db,
                module=module,
                group_name=selected_group_name,
                group_config=group_config,
                page_items=page_items,
                client=client,
                settings=settings,
                task_id=task_id,
                _task_update=_task_update,
                _progress=_progress,
            )
        finally:
            if original_album_name is _ALBUM_NAME_SENTINEL:
                if hasattr(settings, "_generation_album_name"):
                    delattr(settings, "_generation_album_name")
            else:
                settings._generation_album_name = original_album_name

        source_asset, people_context = await _resolve_generation_source_context(
            page=page,
            result=result,
            client=client,
            task_id=task_id,
        )

        artifacts = await _build_generation_artifacts(
            db=db,
            client=client,
            source_asset=source_asset,
            people_context=people_context,
            result=result,
            module=module,
            group_name=selected_group_name,
            settings=settings,
            task_id=task_id,
            _task_update=_task_update,
            _progress=_progress,
            photo_selection_trace=photo_selection_trace,
        )

        return await _persist_generation_outputs(
            db=db,
            task_id=task_id,
            result=result,
            artifacts=artifacts,
            output_path=output_path,
            image_url=image_url,
            schedule_id=schedule_id,
            album_name=album_name,
            notification_presets=notification_presets,
            webhook_url=webhook_url,
            pipeline_start_time=pipeline_start_time,
            _task_update=_task_update,
            _progress=_progress,
        )
    except AIUsageLimitExceededError as exc:
        debug_log("Generation blocked by AI usage limit", task_id=task_id, module=selected_group_name, error=str(exc))
        logger.warning("Generation blocked for task %s: %s", task_id, exc)
        _record_generation_failure(
            db=db,
            task_id=task_id,
            group_name=selected_group_name,
            settings=settings,
            exc=exc,
            current_progress=current_progress,
            _task_update=_task_update,
        )
        return None
    except Exception as exc:
        debug_log("Generation cycle FAILED", task_id=task_id, module=selected_group_name, error=str(exc))
        logger.exception("Generation cycle failed for task %s: %s", task_id, exc)
        _record_generation_failure(
            db=db,
            task_id=task_id,
            group_name=selected_group_name,
            settings=settings,
            exc=exc,
            current_progress=current_progress,
            _task_update=_task_update,
        )
        return None


def _failed_history_provider(group_name: str, settings: SettingsModel) -> tuple[str, str | None]:
    if group_name.startswith("ai_"):
        provider = (settings.ai_image_provider or "").strip().lower() or "unknown"
        model = (settings.ai_image_model or "").strip() or None
        return provider, model
    return "local", None


def _record_generation_failure(
    *,
    db: Session,
    task_id: str,
    group_name: str,
    settings: SettingsModel,
    exc: Exception,
    current_progress: float,
    _task_update: Callable[..., None],
) -> None:
    _task_update(status="failed", step="failed", progress=current_progress, error=str(exc))
    _trace_stage(
        db,
        task_id,
        stage="failed",
        message=str(exc),
        step="failed",
        status="failed",
        progress=current_progress,
        details={"error_type": exc.__class__.__name__},
    )
    try:
        failed_provider, failed_model = _failed_history_provider(group_name, settings)
        upsert_history_entry(
            db,
            task_id,
            generation_type=group_name,
            status="FAILED",
            title=f"Failed: {group_name}",
            summary=str(exc),
            source_asset_ids="[]",
            output_path=None,
            image_url=None,
            provider=failed_provider,
            model=failed_model,
            config_json=json.dumps({"error": str(exc)}),
            task_step="failed",
        )
    except Exception:
        logger.exception("Could not save FAILED history entry for task %s", task_id)


def _merge_module_defaults(groups_config: dict) -> dict:
    from app.services.generation import engine as engine_module

    modules = getattr(engine_module, "MODULES", {}) or {}
    merged = {}
    for name, module in modules.items():
        current = groups_config.get(name) if isinstance(groups_config, dict) else None
        if not isinstance(current, dict):
            current = {}
        in_preset = isinstance(groups_config, dict) and name in groups_config
        merged[name] = {
            "enabled": current.get("enabled", False) if in_preset else False,
            "weight": current.get("weight", module.default_weight),
            "config": {
                **(module.default_config or {}),
                **(current.get("config") if isinstance(current.get("config"), dict) else {}),
            },
        }
    return merged
