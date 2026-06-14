from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.immich.errors import (
    ImmichAuthenticationError,
    ImmichConfigurationError,
    ImmichConnectionError,
    ImmichPermissionError,
    ImmichUnexpectedResponseError,
)
from app.limiter import limiter
from app.schemas.settings import AvailableModelsResponse, ConnectionTestResponse, SettingsResponse, SettingsUpdate
from app.security import decrypt_secret, encrypt_secret, require_auth
from app.services.generation.ai_vision import XIAOMI_API_BASE_URL
from app.services.immich import build_immich_client, get_or_create_settings
from app.services.local_ai import LocalAIConfigurationError, get_local_ai_api_key, get_local_ai_base_url
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


@router.get("/models/{provider}", response_model=AvailableModelsResponse)
async def get_provider_models(
    provider: str, db: Session = Depends(get_db), _: None = Depends(require_auth)
) -> AvailableModelsResponse:
    import httpx

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

        if provider == "gemini":
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

        elif provider == "openai":
            models_list = payload.get("data", [])
            for m in models_list:
                model_id = m.get("id", "")
                if "gpt-4o" in model_id or "gpt-4-vision" in model_id or "gpt-4" in model_id:
                    vision_models.append({"label": model_id, "value": model_id})
                elif "dall-e" in model_id or "gpt-image" in model_id:
                    image_models.append({"label": model_id, "value": model_id})

        elif provider == "openrouter":
            models_list = payload.get("data", [])
            for m in models_list:
                model_id = m.get("id", "")
                name = m.get("name", model_id)
                # Check typical vision/multimodal models
                if any(x in model_id.lower() for x in ["vision", "-vl", "llava", "gemini-2", "gpt-4o", "claude-3"]):
                    vision_models.append({"label": name, "value": model_id})
                if any(x in model_id.lower() for x in ["flux", "stable-diffusion", "midjourney", "dall-e", "imagen"]):
                    image_models.append({"label": name, "value": model_id})

        elif provider == "byteplus":
            models_list = payload.get("data", [])
            for m in models_list:
                model_id = m.get("id", "")
                name = m.get("name", model_id)
                domain = m.get("domain", "")
                task_types = m.get("task_type") or []
                if not isinstance(task_types, list):
                    task_types = []
                
                # AI Vision / VLM models (img2txt / VisualQuestionAnswering)
                if "VisualQuestionAnswering" in task_types or domain == "VLM":
                    vision_models.append({"label": name, "value": model_id})
                
                # AI Image / ImageGeneration models (txt2img / img2img)
                if "TextToImage" in task_types or "ImageToImage" in task_types or domain == "ImageGeneration":
                    image_models.append({"label": name, "value": model_id})

        elif provider == "local":
            models_list = payload.get("data", [])
            for m in models_list:
                model_id = m.get("id", "")
                vision_models.append({"label": model_id, "value": model_id})
                image_models.append({"label": model_id, "value": model_id})

        elif provider == "xiaomi":
            models_list = payload.get("models", [])
            for m in models_list:
                model_id = m.get("id", "")
                name = m.get("name", model_id)
                if "mimo" in model_id.lower():
                    vision_models.append({"label": name, "value": model_id})

        # Ensure fallback lists are used if filtered results are empty
        return AvailableModelsResponse(
            vision_models=vision_models if vision_models else fallback_vision,
            image_models=image_models if image_models else fallback_image,
        )

    except Exception:
        return AvailableModelsResponse(vision_models=fallback_vision, image_models=fallback_image)
