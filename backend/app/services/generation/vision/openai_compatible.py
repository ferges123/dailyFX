from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, NoReturn

import httpx

from app.utils.safe_logging import redact_sensitive

from .base import AIVisionError, AIVisionResult, _chat_image_content, _vision_result_from_chat_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    provider: str
    display_name: str
    url: str
    headers: dict[str, str]
    timeout: float = 30.0


def _raise_operation_error(config: OpenAICompatibleConfig, operation: str, exc: Exception) -> NoReturn:
    safe_error = redact_sensitive(exc)
    logger.error("%s %s error: %s", config.display_name, operation, safe_error)
    raise AIVisionError(f"{config.display_name} {operation} failed: {safe_error}") from exc


def _single_image_content(prompt: str, b64_image: str) -> list[dict[str, Any]]:
    return [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
    ]


async def _chat_completion(
    config: OpenAICompatibleConfig,
    payload: dict[str, Any],
    operation: str,
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            response = await client.post(config.url, headers=config.headers, json=payload)
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("response body is not an object")
        return data
    except Exception as exc:
        _raise_operation_error(config, operation, exc)


async def analyze_images(
    config: OpenAICompatibleConfig,
    b64_images: list[str],
    prompt: str,
    model: str,
) -> AIVisionResult:
    data = await _chat_completion(
        config,
        {
            "model": model,
            "messages": [{"role": "user", "content": _chat_image_content(prompt, b64_images)}],
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
        },
        "multi-image analysis",
    )
    try:
        return _vision_result_from_chat_json(data, provider=config.provider, model=model)
    except Exception as exc:
        _raise_operation_error(config, "multi-image analysis", exc)


async def analyze_image(
    config: OpenAICompatibleConfig,
    b64_image: str,
    prompt: str,
    model: str,
) -> AIVisionResult:
    data = await _chat_completion(
        config,
        {
            "model": model,
            "messages": [{"role": "user", "content": _single_image_content(prompt, b64_image)}],
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
        },
        "analysis",
    )
    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return AIVisionResult(
            title=parsed.get("title", "Untitled"),
            summary=parsed.get("summary", ""),
            tags=[tag for tag in parsed.get("tags", []) if isinstance(tag, str)],
            token_count=data.get("usage", {}).get("total_tokens"),
            provider=config.provider,
            model=model,
        )
    except Exception as exc:
        _raise_operation_error(config, "analysis", exc)


async def describe_image(
    config: OpenAICompatibleConfig,
    b64_image: str,
    prompt: str,
    model: str,
) -> str:
    data = await _chat_completion(
        config,
        {
            "model": model,
            "messages": [{"role": "user", "content": _single_image_content(prompt, b64_image)}],
            "max_tokens": 300,
        },
        "description",
    )
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        _raise_operation_error(config, "description", exc)


async def fuse_prompt(config: OpenAICompatibleConfig, prompt: str, model: str) -> str:
    data = await _chat_completion(
        config,
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
        },
        "prompt fusion",
    )
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        _raise_operation_error(config, "prompt fusion", exc)
