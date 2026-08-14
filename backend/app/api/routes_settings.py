import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database import get_db
from app.immich.errors import ImmichError
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
from app.services.immich import build_immich_client, get_or_create_settings
from app.services.local_ai import get_local_ai_base_url
from app.services.retention import execute_retention, plan_retention
from app.services.settings.connection_tests import (
    _HTTP_PROVIDER_TESTS,
)
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
    except ImmichError as exc:
        msg = f"Immich connection failed: {str(exc)}"
        response = ConnectionTestResponse(ok=False, message=msg, provider="immich")
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


@router.post("/test-provider/{provider}", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def perform_provider_connection_test(
    provider: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    request: Request = None,
    actor_ctx: ActorContext = Depends(get_actor_context),
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    if provider == "local-ai":
        return await _test_local_connection(db, row, actor_ctx)
    elif provider in _HTTP_PROVIDER_TESTS:
        return await _test_provider_connection(db, row, provider, actor_ctx)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")


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


from app.services.settings.provider_models import fetch_provider_models


@router.get("/models/{provider}", response_model=AvailableModelsResponse)
async def get_provider_models(
    provider: str, db: Session = Depends(get_db), _: None = Depends(require_auth)
) -> AvailableModelsResponse:
    return await fetch_provider_models(provider, db, decrypt_secret_fn=decrypt_secret)
