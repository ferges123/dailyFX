from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from io import BytesIO

from PIL import Image
from pillow_heif import register_heif_opener

from app.models.settings import SettingsModel
from app.security import decrypt_secret
from app.services.local_ai import get_local_ai_api_key

register_heif_opener()

logger = logging.getLogger(__name__)

# Default vision models for analysis
OPENAI_VISION_MODEL = "gpt-4o-mini"
GEMINI_VISION_MODEL = "gemini-2.5-flash"
XIAOMI_VISION_MODEL = "mimo-v2.5"
XIAOMI_API_BASE_URL = "https://api.xiaomimimo.com/v1"
XIAOMI_IMAGE_MODELS = {"mimo-v2.5"}


@dataclass(frozen=True)
class AIVisionResult:
    title: str
    summary: str
    tags: list[str] = None
    token_count: int | None = None
    provider: str | None = None
    model: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "tags", self.tags or [])


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


def _validate_xiaomi_image_model(model: str) -> None:
    if model in XIAOMI_IMAGE_MODELS:
        return
    allowed_models = ", ".join(sorted(XIAOMI_IMAGE_MODELS))
    raise AIVisionError(
        f"Xiaomi MiMo image analysis supports only {allowed_models}; model '{model}' is not supported for image input."
    )


DEFAULT_VISION_PROMPT = (
    "Analyze this image. Return a JSON object with three fields: "
    "'title' (a short, creative 3-5 word title), "
    "'summary' (one concise sentence describing the photo), and "
    '\'tags\' (a list of 3-6 descriptive keyword strings, e.g. ["sunset", "beach", "family"]). '
    "Do not use markdown formatting like ```json, just return the raw JSON object."
)


def _chat_image_content(prompt: str, b64_images: list[str]) -> list[dict[str, object]]:
    content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
    for index, b64_image in enumerate(b64_images, start=1):
        content.append({"type": "text", "text": f"Candidate {index}"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}})
    return content


def _vision_result_from_chat_json(data: dict, *, provider: str, model: str) -> AIVisionResult:
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content.strip().replace("```json", "").replace("```", "").strip())
    return AIVisionResult(
        title=parsed.get("title", "Ranking"),
        summary=json.dumps(parsed),
        tags=[t for t in parsed.get("tags", []) if isinstance(t, str)],
        token_count=data.get("usage", {}).get("total_tokens"),
        provider=provider,
        model=model,
    )
