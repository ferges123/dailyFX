import time

import httpx
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.immich.errors import ImmichError
from app.security import decrypt_secret, require_auth
from app.services.generation.ai_vision import XIAOMI_API_BASE_URL
from app.services.immich import build_immich_client, get_or_create_settings
from app.services.local_ai import LocalAIConfigurationError, get_local_ai_api_key, get_local_ai_base_url
from app.version import APP_VERSION

router = APIRouter(prefix="/api", tags=["health"])


def _check_scheduler_health(data_dir) -> dict:
    scheduler_health_path = data_dir / "scheduler.health"
    if not scheduler_health_path.exists():
        return {"status": "missing", "detail": "No scheduler heartbeat yet"}
    age_seconds = max(0, int(time.time() - scheduler_health_path.stat().st_mtime))
    if age_seconds > 120:
        return {
            "status": "stale",
            "age_seconds": age_seconds,
            "detail": "Scheduler heartbeat is stale",
        }
    return {"status": "ok", "age_seconds": age_seconds}


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "auth_enabled": bool(get_settings().app_access_token),
    }


@router.get("/auth/validate")
def auth_validate(_: None = Depends(require_auth)) -> dict:
    return {"status": "ok"}


@router.get("/health/detailed")
async def health_detailed(db: Session = Depends(get_db), _: None = Depends(require_auth)) -> dict:
    app_settings = get_settings()
    checks: dict[str, dict] = {}

    # DB check
    try:
        await run_in_threadpool(db.execute, text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}

    try:
        checks["scheduler"] = await run_in_threadpool(_check_scheduler_health, app_settings.data_dir)
    except Exception as e:
        checks["scheduler"] = {"status": "error", "detail": str(e)}

    try:
        settings = await run_in_threadpool(get_or_create_settings, db)
        if settings.immich_url:
            result = await build_immich_client(settings).test_connection()
            checks["immich"] = {"status": "ok", "version": result.server_version, "user": result.user_email}
        else:
            checks["immich"] = {"status": "not_configured"}
    except ImmichError as e:
        checks["immich"] = {"status": "error", "detail": str(e)}
    except Exception as e:
        checks["immich"] = {"status": "error", "detail": str(e)}

    try:
        settings = await run_in_threadpool(get_or_create_settings, db)
        provider = settings.default_ai_provider or "none"
        if provider == "none":
            checks["ai"] = {"status": "not_configured"}
        else:
            if provider == "openai":
                key = decrypt_secret(settings.encrypted_openai_api_key)
                url = "https://api.openai.com/v1/models"
                headers = {"Authorization": f"Bearer {key}"} if key else {}
            elif provider == "openrouter":
                key = decrypt_secret(settings.encrypted_openrouter_api_key)
                url = "https://openrouter.ai/api/v1/models"
                headers = {"Authorization": f"Bearer {key}"} if key else {}
            elif provider == "byteplus":
                key = decrypt_secret(settings.encrypted_byteplus_api_key)
                url = "https://ark.ap-southeast.bytepluses.com/api/v3/models"
                headers = {"Authorization": f"Bearer {key}"} if key else {}
            elif provider == "xiaomi":
                key = decrypt_secret(settings.encrypted_xiaomi_api_key)
                url = f"{XIAOMI_API_BASE_URL}/models"
                headers = {"api-key": key} if key else {}
            elif provider == "local":
                try:
                    url = f"{get_local_ai_base_url(settings)}/models"
                except LocalAIConfigurationError as exc:
                    checks["ai"] = {
                        "status": "not_configured",
                        "provider": provider,
                        "detail": str(exc),
                    }
                    return {"status": "degraded", "checks": checks}
                key = get_local_ai_api_key(settings)
                headers = {"Authorization": f"Bearer {key}"} if key else {}
            else:  # gemini
                key = decrypt_secret(settings.encrypted_gemini_api_key)
                url = "https://generativelanguage.googleapis.com/v1beta/models"
                headers = {"x-goog-api-key": key} if key else {}
            if not key:
                checks["ai"] = {"status": "key_missing", "provider": provider}
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(url, headers=headers)
                checks["ai"] = {
                    "status": "ok" if r.status_code < 400 else "error",
                    "provider": provider,
                    "http": r.status_code,
                }
    except Exception as e:
        checks["ai"] = {"status": "error", "detail": str(e)}

    overall = (
        "ok" if all(v["status"] in ("ok", "not_configured", "key_missing") for v in checks.values()) else "degraded"
    )
    return {"status": overall, "checks": checks}
