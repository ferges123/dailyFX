import httpx
import json
import logging
from .base import AIVisionResult, AIVisionError, _chat_image_content, _vision_result_from_chat_json

logger = logging.getLogger(__name__)

async def _analyze_images_with_openrouter(
    api_key: str,
    b64_images: list[str],
    prompt: str,
    model: str,
) -> AIVisionResult:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/YOUR_USERNAME/DailyFX-for-immich",
        "X-Title": "dailyFX",
    }
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
            return _vision_result_from_chat_json(response.json(), provider="openrouter", model=model)
        except Exception as exc:
            logger.error("OpenRouter multi-image vision error: %s", exc)
            raise AIVisionError(f"OpenRouter multi-image analysis failed: {exc}") from exc


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
        "X-Title": "dailyFX",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
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
                provider="openrouter",
                model=model,
            )
        except Exception as exc:
            logger.error("OpenRouter vision error: %s", exc)
            raise AIVisionError(f"OpenRouter analysis failed: {exc}") from exc


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
        "X-Title": "dailyFX",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
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
            logger.error("OpenRouter description error: %s", exc)
            raise AIVisionError(f"OpenRouter description failed: {exc}") from exc


async def _fuse_openrouter(api_key: str, prompt: str, model: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/YOUR_USERNAME/DailyFX-for-immich",
        "X-Title": "dailyFX",
    }
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 300}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("OpenRouter prompt fusion error: %s", exc)
            raise AIVisionError(f"OpenRouter prompt fusion failed: {exc}") from exc
