from .base import OPENAI_VISION_MODEL, AIVisionResult
from .openai_compatible import (
    OpenAICompatibleConfig,
    analyze_image,
    analyze_images,
    describe_image,
    fuse_prompt,
)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


def _config(api_key: str) -> OpenAICompatibleConfig:
    return OpenAICompatibleConfig(
        provider="openai",
        display_name="OpenAI",
        url=OPENAI_API_URL,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )


async def _analyze_images_with_openai(
    api_key: str,
    b64_images: list[str],
    prompt: str,
    model: str = OPENAI_VISION_MODEL,
) -> AIVisionResult:
    return await analyze_images(_config(api_key), b64_images, prompt, model)


async def _analyze_with_openai(
    api_key: str,
    b64_image: str,
    prompt: str,
    model: str = OPENAI_VISION_MODEL,
) -> AIVisionResult:
    return await analyze_image(_config(api_key), b64_image, prompt, model)


async def _get_text_desc_openai(api_key: str, b64_image: str, prompt: str, model: str) -> str:
    return await describe_image(_config(api_key), b64_image, prompt, model)


async def _fuse_openai(api_key: str, prompt: str, model: str) -> str:
    return await fuse_prompt(_config(api_key), prompt, model)
