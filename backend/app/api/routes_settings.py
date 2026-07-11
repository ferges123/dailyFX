import logging

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database import get_db
from app.immich.errors import handle_immich_errors
from app.limiter import limiter
from app.schemas.settings import AvailableModelsResponse, ConnectionTestResponse, SettingsResponse, SettingsUpdate
from app.security import (
    ActorContext,
    decrypt_secret,
    encrypt_secret,
    get_actor_context,
    require_auth,
    resolve_actor_context,
)
from app.services.audit import build_settings_diff, record_audit_event
from app.services.generation.ai_vision import XIAOMI_API_BASE_URL
from app.services.immich import build_immich_client, get_or_create_settings
from app.services.local_ai import get_local_ai_api_key, get_local_ai_base_url
from app.services.retention import execute_retention, plan_retention
from app.services.settings.connection_tests import (
    build_connection_test_response as _connection_test_response,
)
from app.services.settings.connection_tests import (
    test_configured_http_provider as _test_configured_http_provider,
)
from app.services.settings.connection_tests import (
    test_optional_configured_http_provider as _test_optional_configured_http_provider,
)
from app.services.settings.response import build_settings_response

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _retention_payload(preview) -> dict:
    return {
        "files": preview.files,
        "metadata": preview.metadata,
        "tasks": preview.tasks,
        "bytes": preview.bytes,
        "missing_files": preview.missing_files,
        "orphan_files": preview.orphan_files,
        "audits": getattr(preview, "audits", 0),
        "warnings": list(preview.warnings),
    }


_HTTP_PROVIDER_TESTS = {
    "openai": {
        "encrypted_field": "encrypted_openai_api_key",
        "url": "https://api.openai.com/v1/models",
        "header_name": "Authorization",
        "provider_name": "OpenAI",
        "use_bearer": True,
    },
    "gemini": {
        "encrypted_field": "encrypted_gemini_api_key",
        "url": "https://generativelanguage.googleapis.com/v1beta/models",
        "header_name": "x-goog-api-key",
        "provider_name": "Gemini",
        "use_bearer": False,
    },
    "openrouter": {
        "encrypted_field": "encrypted_openrouter_api_key",
        "url": "https://openrouter.ai/api/v1/models",
        "header_name": "Authorization",
        "provider_name": "OpenRouter",
        "use_bearer": True,
    },
    "byteplus": {
        "encrypted_field": "encrypted_byteplus_api_key",
        "url": "https://ark.ap-southeast.bytepluses.com/api/v3/models",
        "header_name": "Authorization",
        "provider_name": "BytePlus",
        "use_bearer": True,
    },
    "xiaomi": {
        "encrypted_field": "encrypted_xiaomi_api_key",
        "url": f"{XIAOMI_API_BASE_URL}/models",
        "header_name": "api-key",
        "provider_name": "Xiaomi MiMo",
        "use_bearer": False,
    },
}


def _update_secret(existing: str | None, new_value: str | None) -> str | None:
    if new_value is None:
        return existing
    if new_value == "":
        return None
    return encrypt_secret(new_value)


@router.get("", response_model=SettingsResponse)
def read_settings(db: Session = Depends(get_db), _: None = Depends(require_auth)) -> SettingsResponse:
    row = get_or_create_settings(db)
    return build_settings_response(row)


@router.get("/retention/preview")
def retention_preview(db: Session = Depends(get_db), _: None = Depends(require_auth)) -> dict:
    row = get_or_create_settings(db)
    return _retention_payload(plan_retention(db, row))


@router.post("/retention/run")
def retention_run(
    dry_run: bool = True,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
) -> dict:
    actor_ctx = resolve_actor_context(actor_ctx)
    row = get_or_create_settings(db)
    return _retention_payload(execute_retention(db, row, dry_run=dry_run, actor_ctx=actor_ctx))


@router.put("", response_model=SettingsResponse)
@limiter.limit("10/minute")
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    request: Request = None,
    actor_ctx: ActorContext = Depends(get_actor_context),
) -> SettingsResponse:
    actor_ctx = resolve_actor_context(actor_ctx)
    row = get_or_create_settings(db)

    # 1. Capture old settings values for diffing
    old_immich_api_key = decrypt_secret(row.encrypted_immich_api_key) if row.encrypted_immich_api_key else None
    old_openai_api_key = decrypt_secret(row.encrypted_openai_api_key) if row.encrypted_openai_api_key else None
    old_gemini_api_key = decrypt_secret(row.encrypted_gemini_api_key) if row.encrypted_gemini_api_key else None
    old_openrouter_api_key = (
        decrypt_secret(row.encrypted_openrouter_api_key) if row.encrypted_openrouter_api_key else None
    )
    old_byteplus_api_key = decrypt_secret(row.encrypted_byteplus_api_key) if row.encrypted_byteplus_api_key else None
    old_xiaomi_api_key = decrypt_secret(row.encrypted_xiaomi_api_key) if row.encrypted_xiaomi_api_key else None
    old_local_ai_api_key = decrypt_secret(row.encrypted_local_ai_api_key) if row.encrypted_local_ai_api_key else None

    old_dict = {
        "immich_url": row.immich_url,
        "local_ai_base_url": row.local_ai_base_url,
        "ai_vision_hourly_limit": row.ai_vision_hourly_limit,
        "ai_image_hourly_limit": row.ai_image_hourly_limit,
        "debug_mode": row.debug_mode,
        "favorite_albums_json": row.favorite_albums_json,
        "ai_custom_prompt": row.ai_custom_prompt,
        "retention_enabled": getattr(row, "retention_enabled", True),
        "retention_rejected_files_days": getattr(row, "retention_rejected_files_days", 7),
        "retention_rejected_metadata_days": getattr(row, "retention_rejected_metadata_days", 90),
        "retention_failed_files_days": getattr(row, "retention_failed_files_days", 7),
        "retention_failed_metadata_days": getattr(row, "retention_failed_metadata_days", 90),
        "retention_uploaded_files_days": getattr(row, "retention_uploaded_files_days", 30),
        "retention_uploaded_metadata_days": getattr(row, "retention_uploaded_metadata_days", 30),
        "retention_task_days": getattr(row, "retention_task_days", 30),
        "retention_audit_days": getattr(row, "retention_audit_days", 180),
        "retention_backup_count": getattr(row, "retention_backup_count", 7),
        "immich_api_key": old_immich_api_key,
        "openai_api_key": old_openai_api_key,
        "gemini_api_key": old_gemini_api_key,
        "openrouter_api_key": old_openrouter_api_key,
        "byteplus_api_key": old_byteplus_api_key,
        "xiaomi_api_key": old_xiaomi_api_key,
        "local_ai_api_key": old_local_ai_api_key,
    }

    # 2. Update values
    row.immich_url = payload.immich_url
    row.local_ai_base_url = payload.local_ai_base_url
    row.ai_vision_hourly_limit = payload.ai_vision_hourly_limit
    row.ai_image_hourly_limit = payload.ai_image_hourly_limit
    row.debug_mode = payload.debug_mode
    row.favorite_albums_json = payload.favorite_albums_json
    row.ai_custom_prompt = payload.ai_custom_prompt
    row.retention_enabled = payload.retention_enabled
    row.retention_rejected_files_days = payload.retention_rejected_files_days
    row.retention_rejected_metadata_days = payload.retention_rejected_metadata_days
    row.retention_failed_files_days = payload.retention_failed_files_days
    row.retention_failed_metadata_days = payload.retention_failed_metadata_days
    row.retention_uploaded_files_days = payload.retention_uploaded_files_days
    row.retention_uploaded_metadata_days = payload.retention_uploaded_metadata_days
    row.retention_task_days = payload.retention_task_days
    row.retention_audit_days = payload.retention_audit_days
    row.retention_backup_count = payload.retention_backup_count
    row.encrypted_immich_api_key = _update_secret(row.encrypted_immich_api_key, payload.immich_api_key)
    row.encrypted_openai_api_key = _update_secret(row.encrypted_openai_api_key, payload.openai_api_key)
    row.encrypted_gemini_api_key = _update_secret(row.encrypted_gemini_api_key, payload.gemini_api_key)
    row.encrypted_openrouter_api_key = _update_secret(row.encrypted_openrouter_api_key, payload.openrouter_api_key)
    row.encrypted_byteplus_api_key = _update_secret(row.encrypted_byteplus_api_key, payload.byteplus_api_key)
    row.encrypted_xiaomi_api_key = _update_secret(row.encrypted_xiaomi_api_key, payload.xiaomi_api_key)
    row.encrypted_local_ai_api_key = _update_secret(row.encrypted_local_ai_api_key, payload.local_ai_api_key)
    db.add(row)
    db.commit()
    db.refresh(row)

    # 3. Build new dict for diffing and log audit event
    new_dict = {
        "immich_url": payload.immich_url,
        "local_ai_base_url": payload.local_ai_base_url,
        "ai_vision_hourly_limit": payload.ai_vision_hourly_limit,
        "ai_image_hourly_limit": payload.ai_image_hourly_limit,
        "debug_mode": payload.debug_mode,
        "favorite_albums_json": payload.favorite_albums_json,
        "ai_custom_prompt": payload.ai_custom_prompt,
        "retention_enabled": payload.retention_enabled,
        "retention_rejected_files_days": payload.retention_rejected_files_days,
        "retention_rejected_metadata_days": payload.retention_rejected_metadata_days,
        "retention_failed_files_days": payload.retention_failed_files_days,
        "retention_failed_metadata_days": payload.retention_failed_metadata_days,
        "retention_uploaded_files_days": payload.retention_uploaded_files_days,
        "retention_uploaded_metadata_days": payload.retention_uploaded_metadata_days,
        "retention_task_days": payload.retention_task_days,
        "retention_audit_days": payload.retention_audit_days,
        "retention_backup_count": payload.retention_backup_count,
        "immich_api_key": old_immich_api_key if payload.immich_api_key == "********" else payload.immich_api_key,
        "openai_api_key": old_openai_api_key if payload.openai_api_key == "********" else payload.openai_api_key,
        "gemini_api_key": old_gemini_api_key if payload.gemini_api_key == "********" else payload.gemini_api_key,
        "openrouter_api_key": old_openrouter_api_key
        if payload.openrouter_api_key == "********"
        else payload.openrouter_api_key,
        "byteplus_api_key": old_byteplus_api_key
        if payload.byteplus_api_key == "********"
        else payload.byteplus_api_key,
        "xiaomi_api_key": old_xiaomi_api_key if payload.xiaomi_api_key == "********" else payload.xiaomi_api_key,
        "local_ai_api_key": old_local_ai_api_key
        if payload.local_ai_api_key == "********"
        else payload.local_ai_api_key,
    }

    diff = build_settings_diff(old_dict, new_dict)
    if diff:
        record_audit_event(
            db=db,
            action="settings.updated",
            category="settings",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            summary="Application settings updated",
            changes=diff,
        )

    return build_settings_response(row)


@router.post("/test-immich", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_immich_connection(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    request: Request = None,
    actor_ctx: ActorContext = Depends(get_actor_context),
) -> ConnectionTestResponse:
    actor_ctx = resolve_actor_context(actor_ctx)
    row = get_or_create_settings(db)
    ok = False
    msg = ""
    try:
        with handle_immich_errors():
            result = await build_immich_client(row).test_connection()
        ok = True
        msg = "Immich connection succeeded"
        response = _connection_test_response(
            "immich",
            message=msg,
            server_url=result.server_url,
            user_email=result.user_email,
            user_id=result.user_id,
            server_version=result.server_version,
        )
    except Exception as exc:
        msg = f"Immich connection failed: {str(exc)}"
        response = ConnectionTestResponse(ok=False, message=msg, provider="immich")
        raise
    finally:
        record_audit_event(
            db=db,
            action="settings.connection_tested",
            category="settings",
            outcome="success" if ok else "failure",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            summary=f"Tested connection to Immich: {'success' if ok else 'failed'}",
            metadata={"message": msg},
        )
    return response


@router.post("/test-openai", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_openai_connection(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    request: Request = None,
    actor_ctx: ActorContext = Depends(get_actor_context),
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    return await _test_provider_connection(db, row, "openai", actor_ctx)


@router.post("/test-gemini", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_gemini_connection(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    request: Request = None,
    actor_ctx: ActorContext = Depends(get_actor_context),
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    return await _test_provider_connection(db, row, "gemini", actor_ctx)


@router.post("/test-openrouter", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_openrouter_connection(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    request: Request = None,
    actor_ctx: ActorContext = Depends(get_actor_context),
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    return await _test_provider_connection(db, row, "openrouter", actor_ctx)


@router.post("/test-byteplus", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_byteplus_connection(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    request: Request = None,
    actor_ctx: ActorContext = Depends(get_actor_context),
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    return await _test_provider_connection(db, row, "byteplus", actor_ctx)


@router.post("/test-xiaomi", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_xiaomi_connection(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    request: Request = None,
    actor_ctx: ActorContext = Depends(get_actor_context),
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    return await _test_provider_connection(db, row, "xiaomi", actor_ctx)


@router.post("/test-local-ai", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_local_ai_connection(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    request: Request = None,
    actor_ctx: ActorContext = Depends(get_actor_context),
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    return await _test_local_connection(db, row, actor_ctx)


async def _test_provider_connection(
    db: Session, row, provider_key: str, actor_ctx: ActorContext
) -> ConnectionTestResponse:
    actor_ctx = resolve_actor_context(actor_ctx)
    config = _HTTP_PROVIDER_TESTS[provider_key]
    ok = False
    msg = ""
    try:
        response = await _test_configured_http_provider(
            row=row,
            provider=provider_key,
            **config,
        )
        ok = response.ok
        msg = response.message
        return response
    except Exception as exc:
        msg = str(exc)
        raise
    finally:
        record_audit_event(
            db=db,
            action="settings.connection_tested",
            category="settings",
            outcome="success" if ok else "failure",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            summary=f"Tested connection to {provider_key.upper()}: {'success' if ok else 'failed'}",
            metadata={"message": msg},
        )


async def _test_local_connection(db: Session, row, actor_ctx: ActorContext) -> ConnectionTestResponse:
    actor_ctx = resolve_actor_context(actor_ctx)
    base_url = get_local_ai_base_url(row)
    ok = False
    msg = ""
    try:
        response = await _test_optional_configured_http_provider(
            row=row,
            encrypted_field="encrypted_local_ai_api_key",
            provider="local",
            url=f"{base_url}/models",
            header_name="Authorization",
            provider_name="Local AI",
            use_bearer=True,
        )
        ok = response.ok
        msg = response.message
        return response
    except Exception as exc:
        msg = str(exc)
        raise
    finally:
        record_audit_event(
            db=db,
            action="settings.connection_tested",
            category="settings",
            outcome="success" if ok else "failure",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            summary=f"Tested connection to Local AI: {'success' if ok else 'failed'}",
            metadata={"message": msg},
        )


def _parse_gemini_models(payload: dict) -> tuple[list[dict], list[dict]]:
    vision_models = []
    image_models = []
    models_list = payload.get("models", [])
    for m in models_list:
        name = m.get("name", "")
        display_name = m.get("displayName", name)
        short_name = name.replace("models/", "")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods:
            if "image" in name or "imagen" in name:
                image_models.append({"label": display_name, "value": short_name})
            else:
                vision_models.append({"label": display_name, "value": short_name})
    return vision_models, image_models


def _parse_openai_models(payload: dict) -> tuple[list[dict], list[dict]]:
    vision_models = []
    image_models = []
    models_list = payload.get("data", [])
    for m in models_list:
        model_id = m.get("id", "")
        if "gpt-4o" in model_id or "gpt-4-vision" in model_id or "gpt-4" in model_id:
            vision_models.append({"label": model_id, "value": model_id})
        elif "dall-e" in model_id or "gpt-image" in model_id:
            image_models.append({"label": model_id, "value": model_id})
    return vision_models, image_models


def _parse_openrouter_models(payload: dict) -> tuple[list[dict], list[dict]]:
    vision_models = []
    image_models = []
    models_list = payload.get("data", [])
    for m in models_list:
        model_id = m.get("id", "")
        name = m.get("name", model_id)
        if any(x in model_id.lower() for x in ["vision", "-vl", "llava", "gemini-2", "gpt-4o", "claude-3"]):
            vision_models.append({"label": name, "value": model_id})
        if any(x in model_id.lower() for x in ["flux", "stable-diffusion", "midjourney", "dall-e", "imagen"]):
            image_models.append({"label": name, "value": model_id})
    return vision_models, image_models


def _parse_byteplus_models(payload: dict) -> tuple[list[dict], list[dict]]:
    vision_models = []
    image_models = []
    models_list = payload.get("data", [])
    for m in models_list:
        model_id = m.get("id", "")
        name = m.get("name", model_id)
        domain = m.get("domain", "")
        task_types = m.get("task_type") or []
        if not isinstance(task_types, list):
            task_types = []

        if "VisualQuestionAnswering" in task_types or domain == "VLM":
            vision_models.append({"label": name, "value": model_id})

        if "ImageToImage" in task_types:
            if "seededit" not in model_id.lower():
                image_models.append({"label": name, "value": model_id})
    return vision_models, image_models


def _parse_local_models(payload: dict) -> tuple[list[dict], list[dict]]:
    vision_models = []
    image_models = []
    models_list = payload.get("data", [])
    for m in models_list:
        model_id = m.get("id", "")
        vision_models.append({"label": model_id, "value": model_id})
        image_models.append({"label": model_id, "value": model_id})
    return vision_models, image_models


def _parse_xiaomi_models(payload: dict) -> tuple[list[dict], list[dict]]:
    vision_models = []
    image_models = []
    models_list = payload.get("models", [])
    for m in models_list:
        model_id = m.get("id", "")
        name = m.get("name", model_id)
        if "mimo" in model_id.lower():
            vision_models.append({"label": name, "value": model_id})
    return vision_models, image_models


_PROVIDER_PARSERS = {
    "gemini": _parse_gemini_models,
    "openai": _parse_openai_models,
    "openrouter": _parse_openrouter_models,
    "byteplus": _parse_byteplus_models,
    "local": _parse_local_models,
    "xiaomi": _parse_xiaomi_models,
}


@router.get("/models/{provider}", response_model=AvailableModelsResponse)
async def get_provider_models(
    provider: str, db: Session = Depends(get_db), _: None = Depends(require_auth)
) -> AvailableModelsResponse:
    row = get_or_create_settings(db)

    # Fallback default hardcoded lists
    fallback_vision = []
    fallback_image = []
    if provider == "openai":
        fallback_vision = [{"label": "gpt-4o-mini", "value": "gpt-4o-mini"}, {"label": "gpt-4o", "value": "gpt-4o"}]
        fallback_image = [
            {"label": "gpt-image-1", "value": "gpt-image-1"},
            {"label": "gpt-image-1-mini", "value": "gpt-image-1-mini"},
        ]
    elif provider == "gemini":
        fallback_vision = [
            {"label": "gemini-2.5-flash", "value": "gemini-2.5-flash"},
            {"label": "gemini-2.5-pro", "value": "gemini-2.5-pro"},
            {"label": "gemini-2.0-flash", "value": "gemini-2.0-flash"},
            {"label": "gemini-2.0-flash-lite", "value": "gemini-2.0-flash-lite"},
        ]
        fallback_image = [
            {"label": "gemini-2.5-flash-image", "value": "gemini-2.5-flash-image"},
            {"label": "gemini-3.1-flash-image-preview", "value": "gemini-3.1-flash-image-preview"},
            {"label": "gemini-3-pro-image-preview", "value": "gemini-3-pro-image-preview"},
        ]
    elif provider == "xiaomi":
        fallback_vision = [{"label": "mimo-v2.5", "value": "mimo-v2.5"}]

    # Fetch configuration for HTTP call
    config = _HTTP_PROVIDER_TESTS.get(provider)
    if not config and provider != "local":
        return AvailableModelsResponse(vision_models=fallback_vision, image_models=fallback_image)

    # Get API key / base URL
    api_key = None
    url = None
    header_name = "Authorization"
    use_bearer = True

    if provider == "local":
        try:
            url = f"{get_local_ai_base_url(row)}/models"
        except Exception:
            return AvailableModelsResponse(vision_models=fallback_vision, image_models=fallback_image)
        api_key = get_local_ai_api_key(row)
    else:
        encrypted_field = config["encrypted_field"]
        api_key = decrypt_secret(getattr(row, encrypted_field, None))
        url = config["url"]
        header_name = config["header_name"]
        use_bearer = config["use_bearer"]

    if not api_key and provider != "local":
        return AvailableModelsResponse(vision_models=fallback_vision, image_models=fallback_image)

    headers = {}
    if api_key:
        headers = {header_name: f"Bearer {api_key}" if use_bearer else api_key}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
        if response.status_code >= 400:
            return AvailableModelsResponse(vision_models=fallback_vision, image_models=fallback_image)

        payload = response.json()
        vision_models = []
        image_models = []

        parser = _PROVIDER_PARSERS.get(provider)
        if parser:
            vision_models, image_models = parser(payload)

        # Ensure fallback lists are used if filtered results are empty
        return AvailableModelsResponse(
            vision_models=vision_models if vision_models else fallback_vision,
            image_models=image_models if image_models else fallback_image,
        )

    except Exception as exc:
        logger.debug("Failed to fetch models for provider %s: %s", provider, exc)
        return AvailableModelsResponse(vision_models=fallback_vision, image_models=fallback_image)
