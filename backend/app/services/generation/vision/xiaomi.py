import json
import logging

import httpx

from .base import (
    XIAOMI_API_BASE_URL,
    XIAOMI_VISION_MODEL,
    AIVisionError,
    AIVisionResult,
    _chat_image_content,
    _validate_xiaomi_image_model,
    _vision_result_from_chat_json,
)

logger = logging.getLogger(__name__)

async def _analyze_images_with_xiaomi(
    api_key: str,
    b64_images: list[str],
    prompt: str,
    model: str = XIAOMI_VISION_MODEL,
) -> AIVisionResult:
    _validate_xiaomi_image_model(model)
    url = f"{XIAOMI_API_BASE_URL}/chat/completions"
    headers = {"Content-Type": "application/json", "api-key": api_key}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _chat_image_content(prompt, b64_images)}],
        "max_completion_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return _vision_result_from_chat_json(response.json(), provider="xiaomi", model=model)
        except httpx.TimeoutException as exc:
            logger.error("Xiaomi multi-image vision error (timeout)", exc_info=True)
            raise AIVisionError("Xiaomi multi-image analysis failed: Request timed out") from exc
        except httpx.HTTPStatusError as exc:
            logger.error("Xiaomi multi-image vision error (HTTP error)", exc_info=True)
            raise AIVisionError(f"Xiaomi multi-image analysis failed: HTTP error {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error("Xiaomi multi-image vision error", exc_info=True)
            raise AIVisionError(f"Xiaomi multi-image analysis failed: {repr(exc)}") from exc


async def _analyze_with_xiaomi(
    api_key: str,
    b64_image: str,
    prompt: str,
    model: str = XIAOMI_VISION_MODEL,
) -> AIVisionResult:
    _validate_xiaomi_image_model(model)
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

    async with httpx.AsyncClient(timeout=60.0) as client:
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
        except httpx.TimeoutException as exc:
            logger.error("Xiaomi vision error (timeout)", exc_info=True)
            raise AIVisionError("Xiaomi analysis failed: Request timed out") from exc
        except httpx.HTTPStatusError as exc:
            logger.error("Xiaomi vision error (HTTP error)", exc_info=True)
            raise AIVisionError(f"Xiaomi analysis failed: HTTP error {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error("Xiaomi vision error", exc_info=True)
            raise AIVisionError(f"Xiaomi analysis failed: {repr(exc)}") from exc


async def _get_text_desc_xiaomi(
    api_key: str,
    b64_image: str,
    prompt: str,
    model: str,
) -> str:
    _validate_xiaomi_image_model(model)
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
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException as exc:
            logger.error("Xiaomi description error (timeout)", exc_info=True)
            raise AIVisionError("Xiaomi description failed: Request timed out") from exc
        except httpx.HTTPStatusError as exc:
            logger.error("Xiaomi description error (HTTP error)", exc_info=True)
            raise AIVisionError(f"Xiaomi description failed: HTTP error {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error("Xiaomi description error", exc_info=True)
            raise AIVisionError(f"Xiaomi description failed: {repr(exc)}") from exc


async def _fuse_xiaomi(api_key: str, prompt: str, model: str) -> str:
    url = f"{XIAOMI_API_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 300,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException as exc:
            logger.error("Xiaomi prompt fusion error (timeout)", exc_info=True)
            raise AIVisionError("Xiaomi prompt fusion failed: Request timed out") from exc
        except httpx.HTTPStatusError as exc:
            logger.error("Xiaomi prompt fusion error (HTTP error)", exc_info=True)
            raise AIVisionError(f"Xiaomi prompt fusion failed: HTTP error {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error("Xiaomi prompt fusion error", exc_info=True)
            raise AIVisionError(f"Xiaomi prompt fusion failed: {repr(exc)}") from exc
