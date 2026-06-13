from __future__ import annotations

import logging

from app.models.settings import SettingsModel
from app.services.generation.ai_budget import reserve_ai_usage

# Import base elements
from .vision.base import (
    DEFAULT_VISION_PROMPT,
    GEMINI_VISION_MODEL,
    OPENAI_VISION_MODEL,
    XIAOMI_API_BASE_URL,  # noqa: F401
    XIAOMI_VISION_MODEL,
    AIVisionError,
    AIVisionResult,
    _decrypt_provider_key,
    _normalize_image_for_vision,
    _validate_xiaomi_image_model,
)

# Import Gemini adapter
from .vision.gemini import (
    _analyze_images_with_gemini,
    _analyze_with_gemini,
    _fuse_gemini,
    _get_text_desc_gemini,
)

# Import Local adapter
from .vision.local import (
    _analyze_images_with_local,
    _analyze_with_local,
    _fuse_local,
    _get_text_desc_local,
)

# Import OpenAI adapter
from .vision.openai import (
    _analyze_images_with_openai,
    _analyze_with_openai,
    _fuse_openai,
    _get_text_desc_openai,
)

# Import OpenRouter adapter
from .vision.openrouter import (
    _analyze_images_with_openrouter,
    _analyze_with_openrouter,
    _fuse_openrouter,
    _get_text_desc_openrouter,
)

# Import Xiaomi adapter
from .vision.xiaomi import (
    _analyze_images_with_xiaomi,
    _analyze_with_xiaomi,
    _fuse_xiaomi,
    _get_text_desc_xiaomi,
)

logger = logging.getLogger(__name__)


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
        constraint_note = (
            "\n\nNote: Do not use placeholders like 'person 1', 'person 2', or 'Person A' in the "
            "final generated title, summary, or description. Instead, refer to them naturally "
            "(e.g., 'a man', 'a woman', 'a child', 'a person', or 'they') based on what is visible in the photo."
        )
        prompt = f"{context_hint}\n\n{prompt}{constraint_note}"
    if provider == "openai":
        reserve_ai_usage(
            "vision",
            limit=getattr(settings, "ai_vision_hourly_limit", 30),
            provider=provider,
            model=model or None,
        )
        return await _analyze_with_openai(api_key, b64_image, prompt, model or OPENAI_VISION_MODEL)
    elif provider == "gemini":
        reserve_ai_usage(
            "vision",
            limit=getattr(settings, "ai_vision_hourly_limit", 30),
            provider=provider,
            model=model or None,
        )
        return await _analyze_with_gemini(api_key, b64_image, prompt, model or GEMINI_VISION_MODEL)
    elif provider == "openrouter":
        reserve_ai_usage(
            "vision",
            limit=getattr(settings, "ai_vision_hourly_limit", 30),
            provider=provider,
            model=model or None,
        )
        return await _analyze_with_openrouter(api_key, b64_image, prompt, model or "google/gemini-2.5-flash")
    elif provider == "xiaomi":
        xiaomi_model = model or XIAOMI_VISION_MODEL
        _validate_xiaomi_image_model(xiaomi_model)
        reserve_ai_usage(
            "vision",
            limit=getattr(settings, "ai_vision_hourly_limit", 30),
            provider=provider,
            model=xiaomi_model,
        )
        return await _analyze_with_xiaomi(api_key, b64_image, prompt, xiaomi_model)
    elif provider == "local":
        reserve_ai_usage(
            "vision",
            limit=getattr(settings, "ai_vision_hourly_limit", 30),
            provider=provider,
            model=model or None,
        )
        return await _analyze_with_local(settings, api_key, b64_image, prompt, model or "")

    raise AIVisionError(f"Unsupported AI provider: {provider}")


async def analyze_images(
    settings: SettingsModel,
    image_bytes_list: list[bytes],
    provider: str | None = None,
    model: str | None = None,
    prompt: str | None = None,
) -> AIVisionResult:
    if provider is None:
        provider = getattr(settings, "default_ai_provider", "none") or "none"
    provider = provider.strip().lower()
    if provider == "none":
        return AIVisionResult(title="Untitled", summary="AI analysis skipped (provider set to none)")

    images = [image_bytes for image_bytes in image_bytes_list[:4] if image_bytes]
    if not images:
        raise AIVisionError("No images provided for AI vision analysis")

    api_key = _decrypt_provider_key(settings, provider)
    b64_images = [_normalize_image_for_vision(image_bytes) for image_bytes in images]

    if model is None:
        model = getattr(settings, "default_ai_model", "")
    model = (model or "").strip()
    prompt = prompt or DEFAULT_VISION_PROMPT

    reserve_ai_usage(
        "vision",
        limit=getattr(settings, "ai_vision_hourly_limit", 30),
        provider=provider,
        model=model or None,
    )

    if provider == "openai":
        return await _analyze_images_with_openai(api_key, b64_images, prompt, model or OPENAI_VISION_MODEL)
    if provider == "gemini":
        return await _analyze_images_with_gemini(api_key, b64_images, prompt, model or GEMINI_VISION_MODEL)
    if provider == "openrouter":
        return await _analyze_images_with_openrouter(api_key, b64_images, prompt, model or "google/gemini-2.5-flash")
    if provider == "xiaomi":
        xiaomi_model = model or XIAOMI_VISION_MODEL
        _validate_xiaomi_image_model(xiaomi_model)
        return await _analyze_images_with_xiaomi(api_key, b64_images, prompt, xiaomi_model)
    if provider == "local":
        return await _analyze_images_with_local(settings, api_key, b64_images, prompt, model or "")

    raise AIVisionError(f"Unsupported AI provider: {provider}")


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
    prompt_parts.extend(
        [
            f"Image description: {image_description}",
            f"Style prompt: {style_prompt}",
            "Fused Prompt:",
        ]
    )
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
