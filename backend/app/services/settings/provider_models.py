import logging

import httpx

from app.schemas.settings import AvailableModelsResponse
from app.services.immich import get_or_create_settings
from app.services.local_ai import get_local_ai_api_key, get_local_ai_base_url
from app.services.settings.connection_tests import _HTTP_PROVIDER_TESTS

logger = logging.getLogger(__name__)


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


async def fetch_provider_models(provider: str, db, decrypt_secret_fn=None) -> AvailableModelsResponse:
    if decrypt_secret_fn is None:
        from app.security import decrypt_secret as default_decrypt

        decrypt_secret_fn = default_decrypt

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

    config = _HTTP_PROVIDER_TESTS.get(provider)
    if not config and provider != "local":
        return AvailableModelsResponse(vision_models=fallback_vision, image_models=fallback_image)

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
        try:
            api_key = decrypt_secret_fn(getattr(row, encrypted_field, None))
        except Exception:
            api_key = None
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

        return AvailableModelsResponse(
            vision_models=vision_models if vision_models else fallback_vision,
            image_models=image_models if image_models else fallback_image,
        )

    except Exception as exc:
        logger.debug("Failed to fetch models for provider %s: %s", provider, exc)
        return AvailableModelsResponse(vision_models=fallback_vision, image_models=fallback_image)
