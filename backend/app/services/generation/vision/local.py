import httpx
import json
import logging
from app.models.settings import SettingsModel
from app.services.local_ai import LocalAIConfigurationError, get_local_ai_base_url
from .base import AIVisionResult, AIVisionError, _chat_image_content, _vision_result_from_chat_json

logger = logging.getLogger(__name__)

async def _analyze_images_with_local(
    settings: SettingsModel,
    api_key: str | None,
    b64_images: list[str],
    prompt: str,
    model: str,
) -> AIVisionResult:
    if not model:
        raise AIVisionError("Local AI model is not configured")
    try:
        base_url = get_local_ai_base_url(settings)
    except LocalAIConfigurationError as exc:
        raise AIVisionError(str(exc)) from exc
    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _chat_image_content(prompt, b64_images)}],
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return _vision_result_from_chat_json(response.json(), provider="local", model=model)
        except Exception as exc:
            logger.error("Local AI multi-image vision error: %s", exc)
            raise AIVisionError(f"Local AI multi-image analysis failed: {exc}") from exc


async def _analyze_with_local(
    settings: SettingsModel,
    api_key: str | None,
    b64_image: str,
    prompt: str,
    model: str,
) -> AIVisionResult:
    if not model:
        raise AIVisionError("Local AI model is not configured")
    try:
        base_url = get_local_ai_base_url(settings)
    except LocalAIConfigurationError as exc:
        raise AIVisionError(str(exc)) from exc
    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                    },
                ],
            }
        ],
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return AIVisionResult(
                title=parsed.get("title", "Untitled"),
                summary=parsed.get("summary", ""),
                tags=[t for t in parsed.get("tags", []) if isinstance(t, str)],
                token_count=data.get("usage", {}).get("total_tokens"),
                provider="local",
                model=model,
            )
        except Exception as exc:
            logger.error("Local AI vision error: %s", exc)
            raise AIVisionError(f"Local AI analysis failed: {exc}") from exc


async def _get_text_desc_local(
    settings: SettingsModel,
    api_key: str | None,
    b64_image: str,
    prompt: str,
    model: str,
) -> str:
    if not model:
        raise AIVisionError("Local AI model is not configured")
    try:
        base_url = get_local_ai_base_url(settings)
    except LocalAIConfigurationError as exc:
        raise AIVisionError(str(exc)) from exc
    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                    },
                ],
            }
        ],
        "max_tokens": 300,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("Local AI description error: %s", exc)
            raise AIVisionError(f"Local AI description failed: {exc}") from exc


async def _fuse_local(settings: SettingsModel, api_key: str | None, prompt: str, model: str) -> str:
    if not model:
        raise AIVisionError("Local AI model is not configured")
    try:
        base_url = get_local_ai_base_url(settings)
    except LocalAIConfigurationError as exc:
        raise AIVisionError(str(exc)) from exc
    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("Local AI prompt fusion error: %s", exc)
            raise AIVisionError(f"Local AI prompt fusion failed: {exc}") from exc
