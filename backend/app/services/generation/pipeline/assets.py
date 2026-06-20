import json
import logging
import random
from collections.abc import Callable
from dataclasses import replace

from app.immich.models import ImmichSearchFilters
from app.models.settings import SettingsModel
from app.services.generation.ai_vision import analyze_images
from app.utils.debug_logger import debug_log

from .shared import (
    GenerationModuleSelection,
    GenerationPipelineContext,
    _trace_stage,
)

logger = logging.getLogger(__name__)


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
    return replace(filters, random_size=30)


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


def _recent_source_asset_id_recency(db, *, limit: int = 25) -> dict[str, int]:
    from app.models.generation_history import GenerationHistoryModel

    row_limit = max(limit * 4, limit)
    rows = (
        db.query(GenerationHistoryModel.source_asset_ids)
        .order_by(GenerationHistoryModel.created_at.desc())
        .limit(row_limit)
        .all()
    )

    recency: dict[str, int] = {}
    for row in rows:
        source_ids_json = row[0] if isinstance(row, tuple) else getattr(row, "source_asset_ids", None)
        if not source_ids_json:
            continue
        try:
            source_ids = json.loads(source_ids_json)
        except Exception:
            continue
        if not isinstance(source_ids, list):
            continue
        for source_id in source_ids:
            if not isinstance(source_id, str) or not source_id.strip() or source_id in recency:
                continue
            recency[source_id] = len(recency)
            if len(recency) >= limit:
                return recency
    return recency


def _order_page_items_by_recent_history(page_items: list, recent_source_asset_ids: dict[str, int]) -> list:
    unique_items = _dedupe_page_items(page_items)
    if not unique_items or not recent_source_asset_ids:
        return unique_items

    unused_items = [item for item in unique_items if getattr(item, "id", None) not in recent_source_asset_ids]
    used_items = [item for item in unique_items if getattr(item, "id", None) in recent_source_asset_ids]

    if unused_items:
        random.shuffle(unused_items)

    used_items.sort(key=lambda item: recent_source_asset_ids[getattr(item, "id", "")], reverse=True)
    return unused_items + used_items


def _prepare_page_items_for_module(
    *,
    page,
    module,
    selected_asset_ids: list[str] | None,
    ai_photo_selection_enabled: bool,
    task_id: str,
    _task_update: Callable[..., None],
    recent_source_asset_ids: dict[str, int] | None = None,
) -> list | None:
    page_items = _select_page_items(
        page=page, selected_asset_ids=selected_asset_ids, task_id=task_id, _task_update=_task_update
    )
    if not page_items:
        return None

    # Filter out already processed dailyFX assets for automatic runs (case-insensitive)
    if not selected_asset_ids:
        original_count = len(page_items)
        page_items = [
            item
            for item in page_items
            if not (
                getattr(item, "original_file_name", None)
                and "dailyfx" in getattr(item, "original_file_name", "").lower()
            )
        ]
        removed_count = original_count - len(page_items)
        if removed_count > 0:
            debug_log(
                "Filtered out processed dailyFX assets from selection",
                task_id=task_id,
                removed_count=removed_count,
            )

    unique_items = _dedupe_page_items(page_items)
    if not unique_items:
        return None

    if not selected_asset_ids and recent_source_asset_ids:
        unique_items = _order_page_items_by_recent_history(unique_items, recent_source_asset_ids)
        if not unique_items:
            return None

    source_asset_count = max(1, int(getattr(module, "source_asset_count", 1) or 1))
    if source_asset_count > 1:
        return unique_items[:source_asset_count]
    if ai_photo_selection_enabled:
        return unique_items[:4]
    return unique_items


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
    logger.info("📸 Selected random asset, running module %s (task_id=%s)", ctx.selected_group_name, ctx.task_id)

    ai_photo_selection_enabled = (
        bool(getattr(ctx.settings, "ai_photo_selection_enabled", False))
        and int(getattr(module_selection.module, "source_asset_count", 1) or 1) == 1
    )
    recent_source_asset_ids = (
        _recent_source_asset_id_recency(ctx.db, limit=25) if not ctx.selected_asset_ids else None
    )
    page_items = _prepare_page_items_for_module(
        page=page,
        module=module_selection.module,
        selected_asset_ids=ctx.selected_asset_ids,
        ai_photo_selection_enabled=ai_photo_selection_enabled,
        task_id=ctx.task_id,
        _task_update=ctx.task_update,
        recent_source_asset_ids=recent_source_asset_ids,
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
    return client, page, page_items, photo_selection_trace
