from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from io import BytesIO

import httpx
from PIL import Image
from pillow_heif import register_heif_opener

from app.models.settings import SettingsModel
from app.security import decrypt_secret
from app.services.generation.ai_budget import reserve_ai_usage
from app.services.local_ai import LocalAIConfigurationError, get_local_ai_api_key, get_local_ai_base_url

register_heif_opener()

logger = logging.getLogger(__name__)

# Default vision models for analysis
OPENAI_VISION_MODEL = "gpt-4o-mini"
GEMINI_VISION_MODEL = "gemini-2.5-flash"
XIAOMI_VISION_MODEL = "mimo-v2.5"
XIAOMI_API_BASE_URL = "https://api.xiaomimimo.com/v1"

@dataclass(frozen=True)
class AIVisionResult:
    title: str
    summary: str
    tags: list[str] = None
    token_count: int | None = None
    provider: str | None = None
    model: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'tags', self.tags or [])

class AIVisionError(RuntimeError):
    pass

def _normalize_image_for_vision(image_bytes: bytes) -> str:
    """Resize image to reasonable size for vision processing and return as b64 string."""
    img = Image.open(BytesIO(image_bytes))
    # Max 1024 on any side is usually enough for vision
    img.thumbnail((1024, 1024))
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def _decrypt_provider_key(settings: SettingsModel, provider: str) -> str | None:
    if provider == "openai":
        api_key = decrypt_secret(settings.encrypted_openai_api_key)
    elif provider == "gemini":
        api_key = decrypt_secret(settings.encrypted_gemini_api_key)
    elif provider == "openrouter":
        api_key = decrypt_secret(settings.encrypted_openrouter_api_key)
    elif provider == "xiaomi":
        api_key = decrypt_secret(settings.encrypted_xiaomi_api_key)
    elif provider == "local":
        api_key = get_local_ai_api_key(settings)
    else:
        raise AIVisionError(f"Unsupported AI provider: {provider}")
    if not api_key and provider != "local":
        if provider == "xiaomi":
            raise AIVisionError("Xiaomi MiMo API key is not configured")
        raise AIVisionError(f"{provider.title()} API key is not configured")
    return api_key

DEFAULT_VISION_PROMPT = (
    "Analyze this image. Return a JSON object with three fields: "
    "'title' (a short, creative 3-5 word title), "
    "'summary' (one concise sentence describing the photo), and "
    "'tags' (a list of 3-6 descriptive keyword strings, e.g. [\"sunset\", \"beach\", \"family\"]). "
    "Do not use markdown formatting like ```json, just return the raw JSON object."
)

async def analyze_image(
    settings: SettingsModel,
    image_bytes: bytes,
    provider: str | None = None,
    model: str | None = None,
    prompt: str | None = None,
    context_hint: str | None = None,
) -> AIVisionResult:
    if provider is None:
        provider = getattr(settings, "default_ai_provider", "none") or "none"
    provider = provider.strip().lower()
    if provider == "none":
        return AIVisionResult(title="Untitled", summary="AI analysis skipped (provider set to none)")

    api_key = _decrypt_provider_key(settings, provider)
    b64_image = _normalize_image_for_vision(image_bytes)
    
    if model is None:
        model = getattr(settings, "default_ai_model", "")
    model = (model or "").strip()
    
    prompt = prompt or DEFAULT_VISION_PROMPT
    if context_hint:
        prompt = f"{context_hint}\n\n{prompt}"
    reserve_ai_usage(
        "vision",
        limit=getattr(settings, "ai_vision_hourly_limit", 30),
        provider=provider,
        model=model or None,
    )

    if provider == "openai":
        return await _analyze_with_openai(api_key, b64_image, prompt, model or OPENAI_VISION_MODEL)
    elif provider == "gemini":
        return await _analyze_with_gemini(api_key, b64_image, prompt, model or GEMINI_VISION_MODEL)
    elif provider == "openrouter":
        return await _analyze_with_openrouter(api_key, b64_image, prompt, model or "google/gemini-2.5-flash")
    elif provider == "xiaomi":
        return await _analyze_with_xiaomi(api_key, b64_image, prompt, model or XIAOMI_VISION_MODEL)
    elif provider == "local":
        return await _analyze_with_local(settings, api_key, b64_image, prompt, model or "")

    raise AIVisionError(f"Unsupported AI provider: {provider}")

async def _analyze_with_openai(
    api_key: str,
    b64_image: str,
    prompt: str,
    model: str = OPENAI_VISION_MODEL,
) -> AIVisionResult:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}
                    }
                ]
            }
        ],
        "max_tokens": 300,
        "response_format": {"type": "json_object"}
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
                provider="openai",
                model=model
            )
        except Exception as exc:
            logger.error("OpenAI vision error: %s", exc)
            raise AIVisionError(f"OpenAI analysis failed: {exc}") from exc

async def _analyze_with_gemini(
    api_key: str,
    b64_image: str,
    prompt: str,
    model: str = GEMINI_VISION_MODEL,
) -> AIVisionResult:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": b64_image
                    }
                }
            ]
        }]
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                logger.error("Gemini API Error (%d): %s", response.status_code, response.text[:1000])
            response.raise_for_status()
            data = response.json()
            
            # Gemini response structure is a bit more nested
            text_response = data["candidates"][0]["content"]["parts"][0]["text"]
            # Sometimes Gemini adds markdown code blocks even when asked not to
            clean_text = text_response.strip().replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_text)
            
            return AIVisionResult(
                title=parsed.get("title", "Untitled"),
                summary=parsed.get("summary", ""),
                tags=[t for t in parsed.get("tags", []) if isinstance(t, str)],
                token_count=None,
                provider="gemini",
                model=model
            )
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            body = exc.response.text[:1000] if exc.response is not None else ""
            try:
                payload = exc.response.json() if exc.response is not None else {}
            except ValueError:
                payload = {}
            error = payload.get("error") if isinstance(payload, dict) else {}
            if not isinstance(error, dict):
                error = {}
            request_id = None
            if exc.response is not None:
                request_id = exc.response.headers.get("x-request-id") or exc.response.headers.get("x-goog-request-id")
            logger.error(
                "Gemini vision HTTP error (%s): status=%s message=%s details=%s request_id=%s body=%s",
                status_code,
                error.get("status"),
                error.get("message"),
                error.get("details"),
                request_id,
                body,
            )
            message = error.get("message") or f"HTTP {status_code}"
            raise AIVisionError(f"Gemini analysis failed: {message}") from exc
        except Exception as exc:
            logger.error("Gemini vision error: %s", exc)
            raise AIVisionError("Gemini analysis failed") from exc


async def _analyze_with_openrouter(
    api_key: str,
    b64_image: str,
    prompt: str,
    model: str,
) -> AIVisionResult:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/YOUR_USERNAME/DailyFX-for-immich",
        "X-Title": "dailyFX"
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}
                    }
                ]
            }
        ],
        "max_tokens": 300,
        "response_format": {"type": "json_object"}
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
                provider="openrouter",
                model=model
            )
        except Exception as exc:
            logger.error("OpenRouter vision error: %s", exc)
            raise AIVisionError(f"OpenRouter analysis failed: {exc}") from exc


async def _analyze_with_xiaomi(
    api_key: str,
    b64_image: str,
    prompt: str,
    model: str = XIAOMI_VISION_MODEL,
) -> AIVisionResult:
    url = f"{XIAOMI_API_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }
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
        "max_completion_tokens": 300,
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
                provider="xiaomi",
                model=model,
            )
        except Exception as exc:
            logger.error("Xiaomi vision error: %s", exc)
            raise AIVisionError(f"Xiaomi analysis failed: {exc}") from exc


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


async def describe_image(settings: SettingsModel, image_bytes: bytes, context_hint: str | None = None) -> str:
    provider = getattr(settings, "default_ai_provider", "none") or "none"
    provider = provider.strip().lower()
    if provider == "none":
        return ""

    api_key = _decrypt_provider_key(settings, provider)
    b64_image = _normalize_image_for_vision(image_bytes)
    
    model = getattr(settings, "default_ai_model", "")
    model = (model or "").strip()
    
    prompt = (
        "Describe what you see in this image in detail. Focus on the main subject, "
        "background, lighting, objects, colors, and layout. Keep the description under 100 words, "
        "be direct and descriptive, and return only the raw description text."
    )
    if context_hint:
        prompt = f"{context_hint}\n\n{prompt}"
    
    reserve_ai_usage(
        "vision",
        limit=getattr(settings, "ai_vision_hourly_limit", 30),
        provider=provider,
        model=model or None,
    )

    if provider == "openai":
        return await _get_text_desc_openai(api_key, b64_image, prompt, model or OPENAI_VISION_MODEL)
    elif provider == "gemini":
        return await _get_text_desc_gemini(api_key, b64_image, prompt, model or GEMINI_VISION_MODEL)
    elif provider == "openrouter":
        return await _get_text_desc_openrouter(api_key, b64_image, prompt, model or "google/gemini-2.5-flash")
    elif provider == "xiaomi":
        return await _get_text_desc_xiaomi(api_key, b64_image, prompt, model or XIAOMI_VISION_MODEL)
    elif provider == "local":
        return await _get_text_desc_local(settings, api_key, b64_image, prompt, model or "")

    raise AIVisionError(f"Unsupported AI provider for description: {provider}")


async def _get_text_desc_openai(
    api_key: str,
    b64_image: str,
    prompt: str,
    model: str,
) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}
                    }
                ]
            }
        ],
        "max_tokens": 300
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("OpenAI description error: %s", exc)
            raise AIVisionError(f"OpenAI description failed: {exc}") from exc


async def _get_text_desc_gemini(
    api_key: str,
    b64_image: str,
    prompt: str,
    model: str,
) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": b64_image
                    }
                }
            ]
        }]
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as exc:
            logger.error("Gemini description error: %s", exc)
            raise AIVisionError(f"Gemini description failed: {exc}") from exc


async def _get_text_desc_openrouter(
    api_key: str,
    b64_image: str,
    prompt: str,
    model: str,
) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/YOUR_USERNAME/DailyFX-for-immich",
        "X-Title": "dailyFX"
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}
                    }
                ]
            }
        ],
        "max_tokens": 300
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("OpenRouter description error: %s", exc)
            raise AIVisionError(f"OpenRouter description failed: {exc}") from exc


async def _get_text_desc_xiaomi(
    api_key: str,
    b64_image: str,
    prompt: str,
    model: str,
) -> str:
    url = f"{XIAOMI_API_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }
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
        "max_completion_tokens": 300,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("Xiaomi description error: %s", exc)
            raise AIVisionError(f"Xiaomi description failed: {exc}") from exc


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


async def fuse_prompts(
    settings: SettingsModel,
    image_description: str,
    style_prompt: str,
    context_hint: str | None = None,
) -> str:
    provider = getattr(settings, "default_ai_provider", "none") or "none"
    provider = provider.strip().lower()
    if provider == "none":
        return style_prompt

    api_key = _decrypt_provider_key(settings, provider)
    model = getattr(settings, "default_ai_model", "")
    model = (model or "").strip()
    
    prompt_parts = [
        "You are an AI prompt expert. You are given an image description and a style prompt.",
        "Your task is to rewrite the image description to match the style prompt, merging them into a single, cohesive prompt for an image generation model.",
        "Provide only the final prompt text. Do not include any explanations, introduction, markdown code formatting, or quotation marks.",
    ]
    if context_hint:
        prompt_parts.append(f"Additional context: {context_hint}")
    prompt_parts.extend([
        f"Image description: {image_description}",
        f"Style prompt: {style_prompt}",
        "Fused Prompt:",
    ])
    prompt = "\n".join(prompt_parts)
    
    reserve_ai_usage(
        "vision",
        limit=getattr(settings, "ai_vision_hourly_limit", 30),
        provider=provider,
        model=model or None,
    )

    if provider == "openai":
        return await _fuse_openai(api_key, prompt, model or OPENAI_VISION_MODEL)
    elif provider == "gemini":
        return await _fuse_gemini(api_key, prompt, model or GEMINI_VISION_MODEL)
    elif provider == "openrouter":
        return await _fuse_openrouter(api_key, prompt, model or "google/gemini-2.5-flash")
    elif provider == "xiaomi":
        return await _fuse_xiaomi(api_key, prompt, model or XIAOMI_VISION_MODEL)
    elif provider == "local":
        return await _fuse_local(settings, api_key, prompt, model or "")

    raise AIVisionError(f"Unsupported AI provider for prompt fusion: {provider}")


async def _fuse_openai(api_key: str, prompt: str, model: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 300
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("OpenAI prompt fusion error: %s", exc)
            raise AIVisionError(f"OpenAI prompt fusion failed: {exc}") from exc


async def _fuse_gemini(api_key: str, prompt: str, model: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt}
            ]
        }]
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as exc:
            logger.error("Gemini prompt fusion error: %s", exc)
            raise AIVisionError(f"Gemini prompt fusion failed: {exc}") from exc


async def _fuse_openrouter(api_key: str, prompt: str, model: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/YOUR_USERNAME/DailyFX-for-immich",
        "X-Title": "dailyFX"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 300
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("OpenRouter prompt fusion error: %s", exc)
            raise AIVisionError(f"OpenRouter prompt fusion failed: {exc}") from exc


async def _fuse_xiaomi(api_key: str, prompt: str, model: str) -> str:
    url = f"{XIAOMI_API_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_completion_tokens": 300,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("Xiaomi prompt fusion error: %s", exc)
            raise AIVisionError(f"Xiaomi prompt fusion failed: {exc}") from exc


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
        "messages": [
            {"role": "user", "content": prompt}
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
            logger.error("Local AI prompt fusion error: %s", exc)
            raise AIVisionError(f"Local AI prompt fusion failed: {exc}") from exc
