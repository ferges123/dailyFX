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

    # For explicit manual selection, return selected items as-is (history is still tracked upstream)
    if selected_asset_ids:
        if recent_source_asset_ids:
            used_in_history = [item for item in unique_items if getattr(item, "id", None) in recent_source_asset_ids]
            if used_in_history:
                debug_log(
                    "Manual selection includes previously used assets",
                    task_id=task_id,
                    asset_ids=[getattr(a, "id", None) for a in used_in_history],
                )
        source_asset_count = max(1, int(getattr(module, "source_asset_count", 1) or 1))
        if source_asset_count > 1:
            return unique_items[:source_asset_count]
        return unique_items

    # For automatic runs, prefer unused assets based on history
    if recent_source_asset_ids:
        unused_items = [item for item in unique_items if getattr(item, "id", None) not in recent_source_asset_ids]
        used_items = [item for item in unique_items if getattr(item, "id", None) in recent_source_asset_ids]

        if unused_items:
            random.shuffle(unused_items)
        used_items.sort(key=lambda item: recent_source_asset_ids[getattr(item, "id", "")], reverse=True)

        source_asset_count = max(1, int(getattr(module, "source_asset_count", 1) or 1))
        if source_asset_count > 1:
            ordered = unused_items + used_items
            return ordered[:source_asset_count]

        if ai_photo_selection_enabled:
            if unused_items:
                return unused_items[:4]
            return used_items[:4]
        else:
            if unused_items:
                return unused_items[:1]
            return used_items[:1]

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


def format_polish_date(dt) -> str:
    if dt is None:
        return "nieznanej dacie"
    months = {
        1: "stycznia", 2: "lutego", 3: "marca", 4: "kwietnia",
        5: "maja", 6: "czerwca", 7: "lipca", 8: "sierpnia",
        9: "września", 10: "października", 11: "listopada", 12: "grudnia"
    }
    return f"{dt.day} {months.get(dt.month, '')} {dt.year}"


def polish_plural(count: int, singular: str, plural_234: str, plural_many: str) -> str:
    if count == 1:
        return f"{count} {singular}"
    if 2 <= count % 10 <= 4 and not (12 <= count % 100 <= 14):
        return f"{count} {plural_234}"
    return f"{count} {plural_many}"


async def _pipeline_retrieve_and_select_assets(
    ctx: GenerationPipelineContext,
    module_selection: GenerationModuleSelection,
) -> tuple[object, list[object], dict | None] | None:
    if ctx.filters is None:
        debug_log("Skipping: no filters provided", task_id=ctx.task_id)
        logger.warning("No filters provided, skipping.")
        ctx.task_update(status="failed", step="failed", error="No filters provided")
        return None

    # Determine mode and parameters
    is_manual = bool(ctx.selected_asset_ids)
    required_count = max(1, int(getattr(module_selection.module, "source_asset_count", 1) or 1))
    
    client = None
    page = None
    page_items = []
    ai_photo_selection_enabled = False
    
    # Selection statistics for trace
    candidate_count = 0
    unique_candidate_count = 0
    never_used_count = 0
    released_count = 0
    accepted_count = 0
    pending_excluded_count = 0
    search_attempts = 0
    selection_reason_code = "never_used"
    selection_reason = ""
    
    # Try importing asset usage registry status
    registry_available = True
    try:
        from app.services.generation.asset_usage import get_assets_usage_status
    except Exception as exc:
        logger.warning("Asset usage registry service unavailable: %s", exc)
        registry_available = False

    if is_manual:
        # Manual Selection (direct bypass)
        search_attempts = 1
        client, page = await _search_assets_for_generation(
            settings=ctx.settings,
            filters=_search_filters_for_module(filters=ctx.filters, module=module_selection.module, settings=ctx.settings),
            task_id=ctx.task_id,
            _task_update=ctx.task_update,
            _progress=ctx.progress_msg,
        )
        if not page or not page.items:
            debug_log("Skipping: no assets found", task_id=ctx.task_id)
            logger.warning("No assets found for the given automation filter.")
            ctx.task_update(status="failed", step="failed", error="No assets found for the given automation filter")
            return None

        # Select manual assets
        page_items = _select_page_items(
            page=page, selected_asset_ids=ctx.selected_asset_ids, task_id=ctx.task_id, _task_update=ctx.task_update
        )
        if not page_items:
            return None
        
        # Deduplicate
        page_items = _dedupe_page_items(page_items)
        # Select required count
        page_items = page_items[:required_count]
        
        # Metadata
        candidate_count = len(page.items)
        unique_candidate_count = len(page_items)
        selection_reason_code = "manual_override"
        selection_reason = "Zdjęcie zostało wskazane ręcznie; globalna ochrona przed powtórkami została pominięta."

    else:
        # Automatic Selection with priority rules and up to 3 attempts
        collected_items = []
        seen_ids = set()
        usage_statuses = {}
        
        for attempt in range(3):
            if not registry_available:
                break
                
            search_attempts += 1
            try:
                client, page = await _search_assets_for_generation(
                    settings=ctx.settings,
                    filters=_search_filters_for_module(filters=ctx.filters, module=module_selection.module, settings=ctx.settings),
                    task_id=ctx.task_id,
                    _task_update=ctx.task_update,
                    _progress=ctx.progress_msg,
                )
            except Exception as exc:
                logger.warning("Search attempt %d failed: %s", search_attempts, exc)
                break
            
            if not page or not page.items:
                break
                
            # Filter and deduplicate
            filtered = []
            for item in page.items:
                aid = getattr(item, "id", None)
                if not aid or aid in seen_ids:
                    continue
                # Skip self-generated dailyFX photos
                if getattr(item, "original_file_name", None) and "dailyfx" in getattr(item, "original_file_name", "").lower():
                    continue
                filtered.append(item)
                seen_ids.add(aid)
                
            collected_items.extend(filtered)
            
            # Fetch registry info
            collected_ids = [x.id for x in collected_items]
            try:
                from app.services.generation.asset_usage import get_assets_usage_status
                usage_statuses = get_assets_usage_status(ctx.db, collected_ids)
            except Exception as exc:
                logger.exception("Failed to query registry usage statuses: %s", exc)
                _trace_stage(
                    ctx.db,
                    ctx.task_id,
                    stage="registry_error",
                    message=f"Problem z rejestrem: {exc}",
                    step=ctx.current_step,
                    status="running",
                    progress=ctx.current_progress,
                    details={"error": str(exc)},
                )
                registry_available = False
                break
                
            # Categorize
            never_used = []
            released = []
            accepted = []
            for item in collected_items:
                status = usage_statuses.get(item.id, {})
                if status.get("has_pending"):
                    continue
                if status.get("ever_accepted"):
                    accepted.append(item)
                elif status.get("returned_to_pool"):
                    released.append(item)
                else:
                    never_used.append(item)
                    
            # Stop searching if we have enough of the absolute highest category (never_used)
            if never_used and len(never_used) >= required_count:
                break

        if not registry_available:
            # Fallback mode (using standard recency fallback)
            search_attempts = 1
            client, page = await _search_assets_for_generation(
                settings=ctx.settings,
                filters=_search_filters_for_module(filters=ctx.filters, module=module_selection.module, settings=ctx.settings),
                task_id=ctx.task_id,
                _task_update=ctx.task_update,
                _progress=ctx.progress_msg,
            )
            if not page or not page.items:
                debug_log("Skipping: no assets found in fallback", task_id=ctx.task_id)
                ctx.task_update(status="failed", step="failed", error="No assets found for the given automation filter")
                return None
            
            # Use fallback recency lists
            recent_source_asset_ids = _recent_source_asset_id_recency(ctx.db, limit=25)
            page_items = _prepare_page_items_for_module(
                page=page,
                module=module_selection.module,
                selected_asset_ids=None,
                ai_photo_selection_enabled=False,
                task_id=ctx.task_id,
                _task_update=ctx.task_update,
                recent_source_asset_ids=recent_source_asset_ids,
            )
            if not page_items:
                return None
                
            candidate_count = len(page.items)
            unique_candidate_count = len(page_items)
            selection_reason_code = "registry_unavailable_fallback"
            selection_reason = "Globalny rejestr wykorzystania był niedostępny. Zastosowano awaryjną ochronę przed powtórkami."
            
        else:
            # Categorize the candidates collected across all attempts
            never_used_candidates = []
            released_candidates = []
            accepted_candidates = []
            pending_excluded = []
            
            for item in collected_items:
                status = usage_statuses.get(item.id, {})
                if status.get("has_pending"):
                    pending_excluded.append(item)
                elif status.get("ever_accepted"):
                    accepted_candidates.append(item)
                elif status.get("returned_to_pool"):
                    released_candidates.append(item)
                else:
                    never_used_candidates.append(item)
                    
            candidate_count = len(collected_items)
            unique_candidate_count = len(collected_items) - len(pending_excluded)
            never_used_count = len(never_used_candidates)
            released_count = len(released_candidates)
            accepted_count = len(accepted_candidates)
            pending_excluded_count = len(pending_excluded)
            
            # Sort/shuffle groups
            random.shuffle(never_used_candidates)
            random.shuffle(released_candidates)
            
            # Accepted candidates sorted ascending by last_accepted_at, tie-break on id
            from datetime import datetime, timezone
            epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
            def accepted_sort_key(x):
                status = usage_statuses.get(x.id, {})
                dt = status.get("last_accepted_at") or epoch
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return (dt, x.id)
            accepted_candidates.sort(key=accepted_sort_key)
            
            # Build priority list
            priority_list = never_used_candidates + released_candidates + accepted_candidates
            
            # Apply required asset count selection
            if not priority_list:
                debug_log("Skipping: no available candidates found after exclusions", task_id=ctx.task_id)
                ctx.task_update(status="failed", step="failed", error="No available candidates found after exclusions")
                return None
                
            ai_photo_selection_enabled = (
                bool(getattr(ctx.settings, "ai_photo_selection_enabled", False))
                and required_count == 1
            )
            
            if ai_photo_selection_enabled:
                # Select top 4 from highest available priority group for AI selection
                if never_used_candidates:
                    page_items = never_used_candidates[:4]
                elif released_candidates:
                    page_items = released_candidates[:4]
                else:
                    page_items = accepted_candidates[:4]
            else:
                # Fill positions for multi-source modules sequentially
                page_items = priority_list[:required_count]
                
            # Build Polish selection explanation
            if required_count == 1 and not ai_photo_selection_enabled:
                chosen = page_items[0]
                if chosen in never_used_candidates:
                    selection_reason_code = "never_used"
                    selection_reason = "Wybrano zdjęcie, które nie było wcześniej używane przez DailyFX."
                elif chosen in released_candidates:
                    status = usage_statuses.get(chosen.id, {})
                    reason = status.get("last_release_reason")
                    if reason == "rejected":
                        selection_reason_code = "returned_after_rejection"
                        selection_reason = "Zdjęcie wróciło do puli po odrzuceniu poprzedniego wyniku."
                    elif reason == "failed":
                        selection_reason_code = "returned_after_failure"
                        selection_reason = "Zdjęcie wróciło do puli po nieudanej generacji."
                    else:
                        selection_reason_code = "returned_after_failure"
                        selection_reason = "Zdjęcie wróciło do puli po usunięciu poprzedniego wyniku."
                else:
                    status = usage_statuses.get(chosen.id, {})
                    formatted_date = format_polish_date(status.get("last_accepted_at"))
                    selection_reason_code = "least_recently_accepted"
                    selection_reason = f"Wszystkie dostępne zdjęcia były już zaakceptowane. Wybrano zdjęcie zaakceptowane najdawniej: {formatted_date}."
            elif required_count > 1:
                # Multi-source explanation
                selected_never = len([x for x in page_items if x in never_used_candidates])
                selected_released = len([x for x in page_items if x in released_candidates])
                selected_accepted = len([x for x in page_items if x in accepted_candidates])
                
                if selected_never == len(page_items):
                    selection_reason_code = "never_used"
                    selection_reason = "Wybrano zdjęcia, które nie były wcześniej używane przez DailyFX."
                elif selected_accepted == len(page_items):
                    selection_reason_code = "least_recently_accepted"
                    selection_reason = "Wszystkie dostępne zdjęcia były już zaakceptowane. Wybrano zdjęcia zaakceptowane najdawniej."
                else:
                    selection_reason_code = "mixed_selection"
                    never_str = polish_plural(selected_never, "nowe zdjęcie", "nowe zdjęcia", "nowych zdjęć")
                    accepted_str = polish_plural(selected_accepted, "zdjęcie zaakceptowane najdawniej", "zdjęcia zaakceptowane najdawniej", "zdjęć zaakceptowanych najdawniej")
                    if selected_never > 0 and selected_accepted > 0:
                        selection_reason = f"Wybrano {never_str} i {accepted_str}."
                    elif selected_never > 0:
                        selection_reason = f"Wybrano {never_str}."
                    else:
                        selection_reason = f"Wybrano {accepted_str}."

    # Pack selection trace details
    selected_asset_ids = [getattr(x, "id", None) for x in page_items if getattr(x, "id", None)]
    
    # We set selection metadata on context
    ctx.asset_selection = {
        "policy": "global_usage_registry",
        "mode": "manual" if is_manual else "automatic",
        "candidate_count": candidate_count,
        "unique_candidate_count": unique_candidate_count,
        "never_used_count": never_used_count,
        "released_count": released_count,
        "accepted_count": accepted_count,
        "pending_excluded_count": pending_excluded_count,
        "search_attempts": search_attempts,
        "required_asset_count": required_count,
        "selected_asset_ids": selected_asset_ids,
        "selection_reason_code": selection_reason_code,
        "selection_reason": selection_reason,
    }

    _trace_stage(
        ctx.db,
        ctx.task_id,
        stage="assets_found",
        message=f"Found {unique_candidate_count} candidate assets after registry check",
        step=ctx.current_step,
        status="running",
        progress=ctx.current_progress,
        details={"asset_count": unique_candidate_count},
    )
    
    if not page_items:
        debug_log("Skipping: no assets found after filtering", task_id=ctx.task_id)
        ctx.task_update(status="failed", step="failed", error="No assets found for the given automation filter")
        return None

    debug_log(
        "Random asset selected", task_id=ctx.task_id, count=len(page_items), asset_ids=[a.id for a in page_items[:10]]
    )
    logger.info("📸 Selected assets, running module %s (task_id=%s)", ctx.selected_group_name, ctx.task_id)

    # Handle AI photo selection ranking
    photo_selection_trace = None
    if ai_photo_selection_enabled and len(page_items) > 1:
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
            # Update explanation with the single selected asset ID
            ctx.asset_selection["selected_asset_ids"] = [selected_asset.id]
            # Update explanation reason code and text
            if selected_asset in never_used_candidates:
                ctx.asset_selection["selection_reason_code"] = "never_used"
                ctx.asset_selection["selection_reason"] = "Wybrano zdjęcie, które nie było wcześniej używane przez DailyFX."
            elif selected_asset in released_candidates:
                status = usage_statuses.get(selected_asset.id, {})
                reason = status.get("last_release_reason")
                if reason == "rejected":
                    ctx.asset_selection["selection_reason_code"] = "returned_after_rejection"
                    ctx.asset_selection["selection_reason"] = "Zdjęcie wróciło do puli po odrzuceniu poprzedniego wyniku."
                elif reason == "failed":
                    ctx.asset_selection["selection_reason_code"] = "returned_after_failure"
                    ctx.asset_selection["selection_reason"] = "Zdjęcie wróciło do puli po nieudanej generacji."
                else:
                    ctx.asset_selection["selection_reason_code"] = "returned_after_failure"
                    ctx.asset_selection["selection_reason"] = "Zdjęcie wróciło do puli po usunięciu poprzedniego wyniku."
            else:
                status = usage_statuses.get(selected_asset.id, {})
                formatted_date = format_polish_date(status.get("last_accepted_at"))
                ctx.asset_selection["selection_reason_code"] = "least_recently_accepted"
                ctx.asset_selection["selection_reason"] = f"Wszystkie dostępne zdjęcia były już zaakceptowane. Wybrano zdjęcie zaakceptowane najdawniej: {formatted_date}."
            
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

    if registry_available:
        try:
            from app.services.generation.asset_usage import record_assets_usage_pending
            record_assets_usage_pending(
                ctx.db,
                task_id=ctx.task_id,
                asset_ids=selected_asset_ids,
                generation_type=module_selection.name,
                usage_source="automatic" if ctx.task_id.startswith("auto-") else "manual",
                schedule_id=ctx.schedule_id,
            )
        except Exception as exc:
            logger.exception("Failed to record assets as pending in registry: %s", exc)

    return client, page, page_items, photo_selection_trace
