from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter

from app.immich.errors import (
    ImmichAuthenticationError,
    ImmichConfigurationError,
    ImmichConnectionError,
    ImmichPermissionError,
    ImmichUnexpectedResponseError,
)
from app.schemas.settings import ConnectionTestResponse, SettingsResponse, SettingsUpdate
from app.security import encrypt_secret, require_auth
from app.services.generation.ai_vision import XIAOMI_API_BASE_URL
from app.services.immich import build_immich_client, get_or_create_settings
from app.services.local_ai import LocalAIConfigurationError, get_local_ai_base_url
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
        "header_name": "x-api-key",
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


@router.put("", response_model=SettingsResponse)
@limiter.limit("10/minute")
def update_settings(
    payload: SettingsUpdate, db: Session = Depends(get_db), _: None = Depends(require_auth), request: Request = None
) -> SettingsResponse:
    row = get_or_create_settings(db)
    row.immich_url = payload.immich_url
    row.local_ai_base_url = payload.local_ai_base_url
    row.ai_vision_hourly_limit = payload.ai_vision_hourly_limit
    row.ai_image_hourly_limit = payload.ai_image_hourly_limit
    row.debug_mode = payload.debug_mode
    row.favorite_albums_json = payload.favorite_albums_json
    row.ai_custom_prompt = payload.ai_custom_prompt
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
    return build_settings_response(row)


@router.post("/test-immich", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_immich_connection(
    db: Session = Depends(get_db), _: None = Depends(require_auth), request: Request = None
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    try:
        result = await build_immich_client(row).test_connection()
    except ImmichConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImmichAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ImmichPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ImmichConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ImmichUnexpectedResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _connection_test_response(
        "immich",
        message="Immich connection succeeded",
        server_url=result.server_url,
        user_email=result.user_email,
        user_id=result.user_id,
        server_version=result.server_version,
    )


@router.post("/test-openai", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_openai_connection(
    db: Session = Depends(get_db), _: None = Depends(require_auth), request: Request = None
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    return await _test_provider_connection(row, "openai")


@router.post("/test-gemini", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_gemini_connection(
    db: Session = Depends(get_db), _: None = Depends(require_auth), request: Request = None
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    return await _test_provider_connection(row, "gemini")


@router.post("/test-openrouter", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_openrouter_connection(
    db: Session = Depends(get_db), _: None = Depends(require_auth), request: Request = None
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    return await _test_provider_connection(row, "openrouter")


@router.post("/test-byteplus", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_byteplus_connection(
    db: Session = Depends(get_db), _: None = Depends(require_auth), request: Request = None
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    return await _test_provider_connection(row, "byteplus")


@router.post("/test-xiaomi", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_xiaomi_connection(
    db: Session = Depends(get_db), _: None = Depends(require_auth), request: Request = None
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    return await _test_provider_connection(row, "xiaomi")


@router.post("/test-local-ai", response_model=ConnectionTestResponse)
@limiter.limit("10/minute")
async def test_local_ai_connection(
    db: Session = Depends(get_db), _: None = Depends(require_auth), request: Request = None
) -> ConnectionTestResponse:
    row = get_or_create_settings(db)
    try:
        return await _test_local_connection(row)
    except LocalAIConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _test_provider_connection(row, provider_key: str) -> ConnectionTestResponse:
    config = _HTTP_PROVIDER_TESTS[provider_key]
    return await _test_configured_http_provider(
        row=row,
        provider=provider_key,
        **config,
    )


async def _test_local_connection(row) -> ConnectionTestResponse:
    base_url = get_local_ai_base_url(row)
    return await _test_optional_configured_http_provider(
        row=row,
        encrypted_field="encrypted_local_ai_api_key",
        provider="local",
        url=f"{base_url}/models",
        header_name="Authorization",
        provider_name="Local AI",
        use_bearer=True,
    )
