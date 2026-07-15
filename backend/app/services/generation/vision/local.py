from app.models.settings import SettingsModel
from app.services.local_ai import LocalAIConfigurationError, get_local_ai_base_url

from .base import AIVisionError, AIVisionResult
from .openai_compatible import (
    OpenAICompatibleConfig,
    analyze_image,
    analyze_images,
    describe_image,
    fuse_prompt,
)


def _config(settings: SettingsModel, api_key: str | None) -> OpenAICompatibleConfig:
    try:
        base_url = get_local_ai_base_url(settings)
    except LocalAIConfigurationError as exc:
        raise AIVisionError(str(exc)) from exc

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return OpenAICompatibleConfig(
        provider="local",
        display_name="Local AI",
        url=f"{base_url}/chat/completions",
        headers=headers,
    )


def _require_model(model: str) -> None:
    if not model:
        raise AIVisionError("Local AI model is not configured")


async def _analyze_images_with_local(
    settings: SettingsModel,
    api_key: str | None,
    b64_images: list[str],
    prompt: str,
    model: str,
) -> AIVisionResult:
    _require_model(model)
    return await analyze_images(_config(settings, api_key), b64_images, prompt, model)


async def _analyze_with_local(
    settings: SettingsModel,
    api_key: str | None,
    b64_image: str,
    prompt: str,
    model: str,
) -> AIVisionResult:
    _require_model(model)
    return await analyze_image(_config(settings, api_key), b64_image, prompt, model)


async def _get_text_desc_local(
    settings: SettingsModel,
    api_key: str | None,
    b64_image: str,
    prompt: str,
    model: str,
) -> str:
    _require_model(model)
    return await describe_image(_config(settings, api_key), b64_image, prompt, model)


async def _fuse_local(settings: SettingsModel, api_key: str | None, prompt: str, model: str) -> str:
    _require_model(model)
    return await fuse_prompt(_config(settings, api_key), prompt, model)
