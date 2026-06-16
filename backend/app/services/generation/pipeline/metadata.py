import logging
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models.settings import SettingsModel
from app.services.generation.exif_embedder import embed_exif_metadata
from app.services.generation.people_context import load_people_context
from app.utils.debug_logger import debug_log

from .shared import (
    GenerationArtifacts,
    GenerationModuleSelection,
    GenerationPipelineContext,
    _build_metadata_provenance,
    _trace_stage,
)


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


logger = logging.getLogger(__name__)

FINAL_AI_VISION_PROMPT = (
    "Analyze this final generated image. Describe what is actually visible in the image itself, "
    "not the source photo used to create it. Return a JSON object with three fields: "
    "'title' (a short, creative 3-5 word title), "
    "'summary' (one concise sentence describing the final image), and "
    "'tags' (a list of 3-6 descriptive keyword strings). "
    "Do not use markdown formatting like ```json, just return the raw JSON object."
)


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


def _ai_tag_injections(module, group_name: str) -> list[str]:
    label = getattr(module, "label", group_name) or group_name
    style_tag = label[3:] if isinstance(label, str) and label.startswith("AI ") else label
    injections = ["AI"]
    if style_tag:
        injections.append(style_tag)
    return injections


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
        metadata_provenance["exif_info"]["attempted"] = True
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

        from app.services.generation.output_format import is_animated_output

        if is_animated_output(getattr(result, "output_format", "png")):
            metadata_provenance["exif_info"].update(embedded=False, skip_reason="animated_output")
            final_bytes = result.image_bytes
        else:
            final_bytes = embed_exif_metadata(result.image_bytes, source_asset, state["ai_title"], state["exif_info"])
            metadata_provenance["exif_info"].update(embedded=True, skip_reason=None)
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
