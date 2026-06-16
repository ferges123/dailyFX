from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import httpx
from PIL import Image
from pillow_heif import register_heif_opener

from app.models.settings import SettingsModel
from app.security import decrypt_secret
from app.services.generation.ai_budget import reserve_ai_usage
from app.services.local_ai import LocalAIConfigurationError, get_local_ai_api_key, get_local_ai_base_url
from app.utils.debug_logger import debug_log

register_heif_opener()

OPENAI_IMAGE_MODEL = "gpt-image-1"
GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
OPENAI_IMAGE_MODELS = {"gpt-image-1", "gpt-image-1-mini", "gpt-image-1.5"}
GEMINI_IMAGE_MODELS = {"gemini-2.5-flash-image", "gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"}
PROVIDER_IMAGE_FORMATS = {
    "openai": "png",
    "gemini": "png",
    "openrouter": "jpeg",
    "byteplus": "jpeg",
    "local": "png",
}


@dataclass(frozen=True)
class AIImageResult:
    image_bytes: bytes
    provider: str
    model: str


class AIImageError(RuntimeError):
    pass


def _shorten(value: str, limit: int = 500) -> str:
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _load_input_image(image_bytes: bytes) -> Image.Image:
    image = Image.open(BytesIO(image_bytes))
    w, h = image.size
    max_size = 1024
    if w > max_size or h > max_size:
        if w > h:
            new_w = max_size
            new_h = int(h * (max_size / w))
        else:
            new_h = max_size
            new_w = int(w * (max_size / h))
        image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return image.convert("RGB")


def _byteplus_error_hint(status_code: int, body_text: str) -> str | None:
    text = body_text.lower()
    if status_code in {401, 403} or "unauthorized" in text or "forbidden" in text or "api key" in text:
        return "Check the BytePlus API key and project permissions."
    if status_code == 429 or "rate limit" in text or "too many requests" in text:
        return "BytePlus rate limit hit; retry later or reduce request volume."
    if "model" in text and ("not found" in text or "invalid" in text or "unsupported" in text):
        return "Check the BytePlus model/endpoint ID in settings."
    if "image" in text and ("format" in text or "parse" in text or "decode" in text):
        return "Check the input image format and the BytePlus response shape."
    if status_code >= 500:
        return "BytePlus server-side failure; retry later or inspect the raw response."
    return None


def _byteplus_error_body(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text

    if isinstance(payload, (dict, list)):
        try:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(payload)

    return str(payload)


def _extract_byteplus_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict) and "message" in err:
            return str(err["message"])
        metadata = payload.get("ResponseMetadata")
        if isinstance(metadata, dict):
            err_meta = metadata.get("Error")
            if isinstance(err_meta, dict) and "Message" in err_meta:
                return str(err_meta["Message"])
        msg = payload.get("message")
        if isinstance(msg, str):
            return msg
    return json.dumps(payload, ensure_ascii=False)


def _normalize_input_image(image_bytes: bytes) -> tuple[bytes, str]:
    image = _load_input_image(image_bytes)
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue(), "image/png"


def _normalize_input_image_as_jpeg(image_bytes: bytes, quality: int = 92) -> tuple[bytes, str]:
    image = _load_input_image(image_bytes)
    out = BytesIO()
    image.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue(), "image/jpeg"


def encode_image_for_provider(image_bytes: bytes, provider: str) -> tuple[bytes, str]:
    normalized_provider = (provider or "").strip().lower()
    image_format = PROVIDER_IMAGE_FORMATS.get(normalized_provider)
    if image_format == "png":
        return _normalize_input_image(image_bytes)
    if image_format == "jpeg":
        return _normalize_input_image_as_jpeg(image_bytes)
    raise AIImageError(f"Unsupported AI provider: {provider}")


def _decrypt_provider_key(settings: SettingsModel, provider: str) -> str | None:
    if provider == "openai":
        api_key = decrypt_secret(settings.encrypted_openai_api_key)
    elif provider == "gemini":
        api_key = decrypt_secret(settings.encrypted_gemini_api_key)
    elif provider == "openrouter":
        api_key = decrypt_secret(settings.encrypted_openrouter_api_key)
    elif provider == "byteplus":
        api_key = decrypt_secret(settings.encrypted_byteplus_api_key)
    elif provider == "local":
        api_key = get_local_ai_api_key(settings)
    else:
        raise AIImageError(f"Unsupported AI provider: {provider}")
    if not api_key and provider != "local":
        raise AIImageError(f"{provider.title()} API key is not configured")
    return api_key


def _resolve_provider(settings: SettingsModel) -> str:
    provider = (settings.ai_image_provider or "").strip().lower()
    if provider in {"openai", "gemini", "openrouter", "byteplus", "local"}:
        return provider
    raise AIImageError("Default AI provider is not configured")


def _resolve_model(settings: SettingsModel, provider: str) -> str:
    requested = (settings.ai_image_model or "").strip()
    if provider == "openai":
        return requested if requested in OPENAI_IMAGE_MODELS else OPENAI_IMAGE_MODEL
    if provider == "gemini":
        return requested if requested in GEMINI_IMAGE_MODELS else GEMINI_IMAGE_MODEL
    if provider == "openrouter":
        return requested or "black-forest-labs/flux-1-schnell"
    if provider == "byteplus":
        return requested or ""
    if provider == "local":
        return requested or ""
    raise AIImageError(f"Unsupported AI provider: {provider}")


def _extract_b64_image(payload: Any) -> bytes:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                raw = item.get("b64_json") or item.get("b64Json") or item.get("base64")
                if isinstance(raw, str) and raw.strip():
                    return base64.b64decode(raw)
        candidates = payload.get("candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                content = candidate.get("content")
                if not isinstance(content, dict):
                    continue
                parts = content.get("parts")
                if not isinstance(parts, list):
                    continue
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    inline = part.get("inlineData") or part.get("inline_data")
                    if not isinstance(inline, dict):
                        continue
                    raw = inline.get("data")
                    if isinstance(raw, str) and raw.strip():
                        return base64.b64decode(raw)
        parts = payload.get("parts")
        if isinstance(parts, list):
            for part in parts:
                if not isinstance(part, dict):
                    continue
                inline = part.get("inlineData") or part.get("inline_data")
                if not isinstance(inline, dict):
                    continue
                raw = inline.get("data")
                if isinstance(raw, str) and raw.strip():
                    return base64.b64decode(raw)
    raise AIImageError("AI provider did not return an image")


async def _fetch_image_bytes(image_ref: str) -> bytes:
    if image_ref.startswith("data:"):
        if "base64," in image_ref:
            encoded = image_ref.split("base64,", 1)[1]
            return base64.b64decode(encoded)
        raise AIImageError("Unsupported data URL returned by BytePlus")

    if image_ref.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(image_ref)
            response.raise_for_status()
            return response.content

    return base64.b64decode(image_ref)


async def _generate_with_openai(api_key: str, image_bytes: bytes, prompt: str, model: str) -> bytes:
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/images/edits",
            headers={"Authorization": f"Bearer {api_key}"},
            files=[
                ("image", ("source.png", image_bytes, "image/png")),
            ],
            data={
                "model": model,
                "prompt": prompt,
                "output_format": "png",
            },
        )
    if response.status_code >= 400:
        detail = None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                detail = error.get("message")
            elif isinstance(error, str):
                detail = error
        raise AIImageError(detail or f"OpenAI returned HTTP {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise AIImageError("OpenAI returned a non-JSON response") from exc
    if not isinstance(payload, dict):
        raise AIImageError("OpenAI returned an unexpected response shape")
    return _extract_b64_image(payload)


async def _generate_with_gemini(api_key: str, image_bytes: bytes, prompt: str, model: str) -> bytes:
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": "image/png", "data": encoded_image}},
                ],
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
        },
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=body,
        )
    if response.status_code >= 400:
        detail = None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                detail = error.get("message")
            elif isinstance(error, str):
                detail = error
        raise AIImageError(detail or f"Gemini returned HTTP {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise AIImageError("Gemini returned a non-JSON response") from exc
    return _extract_b64_image(payload)


async def generate_ai_image(
    settings: SettingsModel,
    image_bytes: bytes,
    prompt: str,
    negative_prompt: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    context_hint: str | None = None,
    prompt_enrichment_context_hint: str | None = None,
    faces: list[dict] | None = None,
) -> AIImageResult:
    if provider is None:
        provider = _resolve_provider(settings)
    provider = provider.strip().lower()

    base_prompt = prompt
    if context_hint:
        base_prompt = f"{context_hint}\n\n{base_prompt}"

    if (
        getattr(settings, "ai_prompt_enrichment", False) is True
        and getattr(settings, "default_ai_provider", "none") != "none"
    ):
        try:
            from app.services.generation.ai_vision import describe_image, fuse_prompts

            debug_log("AI prompt enrichment started", original_prompt=prompt)
            enrichment_context = prompt_enrichment_context_hint or context_hint
            desc = await describe_image(settings, image_bytes, context_hint=enrichment_context)
            if desc:
                debug_log("AI vision image description generated", description=desc)
                fused = await fuse_prompts(settings, desc, base_prompt, context_hint=enrichment_context)
                if fused:
                    debug_log("AI prompt enrichment complete", original_prompt=prompt, fused_prompt=fused)
                    base_prompt = fused
        except Exception as exc:
            debug_log("AI prompt enrichment failed, falling back to original prompt", error=str(exc))

    if negative_prompt:
        base_prompt = f"{base_prompt}\nNegative prompt: {negative_prompt}"

    api_key = _decrypt_provider_key(settings, provider)

    if model is None:
        model = _resolve_model(settings, provider)

    if provider in {"openai", "local"}:
        image_bytes = _crop_to_largest_face(image_bytes, faces)

    encoded_image_bytes, mime_type = encode_image_for_provider(image_bytes, provider)

    reserve_ai_usage(
        "image",
        limit=getattr(settings, "ai_image_hourly_limit", 10),
        provider=provider,
        model=model,
    )
    if provider == "openai":
        result = await _generate_with_openai(api_key, encoded_image_bytes, base_prompt, model)
        return AIImageResult(image_bytes=result, provider=provider, model=model)
    if provider == "gemini":
        result = await _generate_with_gemini(api_key, encoded_image_bytes, base_prompt, model)
        return AIImageResult(image_bytes=result, provider=provider, model=model)
    if provider == "openrouter":
        result = await _generate_with_openrouter(api_key, encoded_image_bytes, base_prompt, model, mime_type)
        return AIImageResult(image_bytes=result, provider=provider, model=model)
    if provider == "byteplus":
        result = await _generate_with_byteplus(api_key, encoded_image_bytes, base_prompt, model, mime_type)
        return AIImageResult(image_bytes=result, provider=provider, model=model)
    if provider == "local":
        result = await _generate_with_local(settings, api_key, encoded_image_bytes, base_prompt, model, mime_type)
        return AIImageResult(image_bytes=result, provider=provider, model=model)
    raise AIImageError(f"Unsupported AI provider: {provider}")


async def _generate_with_byteplus(api_key: str, image_bytes: bytes, prompt: str, model: str, mime_type: str) -> bytes:
    if not model:
        raise AIImageError("BytePlus Endpoint ID (model) is not configured")
    url = "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    try:
        import math

        with Image.open(BytesIO(image_bytes)) as img:
            width, height = img.size
        min_pixels = 3686400
        current_pixels = width * height
        if current_pixels < min_pixels:
            scale = math.sqrt(min_pixels / current_pixels)
            w_scaled = int(math.ceil(width * scale))
            h_scaled = int(math.ceil(height * scale))
            width = ((w_scaled + 7) // 8) * 8
            height = ((h_scaled + 7) // 8) * 8
        size_param = f"{width}x{height}"
    except Exception as exc:
        debug_log("Failed to parse image size for BytePlus", error=str(exc))
        size_param = "1k"

    payload = {
        "model": model,
        "prompt": prompt,
        "image": f"data:{mime_type};base64,{b64_image}",
        "size": size_param,
        "response_format": "url",
        "watermark": False,
    }
    debug_log(
        "BytePlus image request",
        url=url,
        model=model,
        prompt_chars=len(prompt),
        image_bytes=len(image_bytes),
        response_format=payload["response_format"],
        watermark=payload["watermark"],
    )
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            debug_log(
                "BytePlus image response",
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                content_length=response.headers.get("content-length"),
            )
            if response.status_code >= 400:
                error_body = _byteplus_error_body(response)
                debug_log(
                    "BytePlus image error response body",
                    status_code=response.status_code,
                    body=_shorten(error_body),
                )
                hint = _byteplus_error_hint(response.status_code, error_body)
                if hint:
                    debug_log("BytePlus image error hint", status_code=response.status_code, hint=hint)

                err_msg = _extract_byteplus_error(response)
                full_msg = f"BytePlus image generation failed (HTTP {response.status_code}): {err_msg}"
                if hint:
                    full_msg += f". Hint: {hint}"
                raise AIImageError(full_msg)
            response.raise_for_status()
            data = response.json()
        except AIImageError:
            raise
        except Exception as exc:
            debug_log("BytePlus image request failed", error=str(exc))
            raise AIImageError(f"BytePlus image generation failed: {exc}") from exc

    try:
        if isinstance(data, dict):
            keys = sorted(data.keys())
            debug_log("BytePlus image response parsed", keys=keys)
            items = data.get("data")
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    url_ref = item.get("url")
                    if isinstance(url_ref, str) and url_ref.strip():
                        debug_log("BytePlus image response returned URL", has_url=True)
                        return await _fetch_image_bytes(url_ref.strip())
                    b64_ref = item.get("b64_json") or item.get("b64Json") or item.get("base64")
                    if isinstance(b64_ref, str) and b64_ref.strip():
                        debug_log("BytePlus image response returned base64", has_base64=True)
                        return base64.b64decode(b64_ref.strip())
                    image_ref = item.get("image")
                    if isinstance(image_ref, str) and image_ref.strip():
                        debug_log("BytePlus image response returned image ref", has_image_ref=True)
                        return await _fetch_image_bytes(image_ref.strip())
            url_ref = data.get("url")
            if isinstance(url_ref, str) and url_ref.strip():
                debug_log("BytePlus image response returned top-level URL", has_url=True)
                return await _fetch_image_bytes(url_ref.strip())
            b64_ref = data.get("b64_json") or data.get("b64Json") or data.get("base64")
            if isinstance(b64_ref, str) and b64_ref.strip():
                debug_log("BytePlus image response returned top-level base64", has_base64=True)
                return base64.b64decode(b64_ref.strip())
    except Exception as exc:
        debug_log("BytePlus image response parsing failed", error=str(exc))
        raise AIImageError(f"Failed to parse image from BytePlus response: {exc}") from exc

    raise AIImageError("BytePlus did not return an image in the expected format")


async def _generate_with_openrouter(api_key: str, image_bytes: bytes, prompt: str, model: str, mime_type: str) -> bytes:
    url = "https://openrouter.ai/api/v1/chat/completions"
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
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
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}},
                ],
            }
        ],
        "modalities": ["image", "text"],
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise AIImageError(f"OpenRouter image generation failed: {exc}") from exc

    try:
        message = data["choices"][0]["message"]
        if "images" in message and isinstance(message["images"], list) and message["images"]:
            b64_data = message["images"][0]
            if "," in b64_data:
                b64_data = b64_data.split(",")[1]
            return base64.b64decode(b64_data)

        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image":
                    img_data = part.get("image") or ""
                    if "," in img_data:
                        img_data = img_data.split(",")[1]
                    return base64.b64decode(img_data)
    except Exception as exc:
        raise AIImageError(f"Failed to parse image from OpenRouter response: {exc}") from exc

    raise AIImageError("OpenRouter did not return an image in the expected format")


async def _generate_with_local(
    settings: SettingsModel,
    api_key: str | None,
    image_bytes: bytes,
    prompt: str,
    model: str,
    mime_type: str,
) -> bytes:
    if not model:
        raise AIImageError("Local AI model is not configured")
    try:
        base_url = get_local_ai_base_url(settings)
    except LocalAIConfigurationError as exc:
        raise AIImageError(str(exc)) from exc
    url = f"{base_url}/images/edits"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            headers=headers,
            files=[("image", ("source.png", image_bytes, mime_type))],
            data={
                "model": model,
                "prompt": prompt,
                "output_format": "png",
            },
        )
    if response.status_code >= 400:
        detail = None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                detail = error.get("message")
            elif isinstance(error, str):
                detail = error
        raise AIImageError(detail or f"Local AI returned HTTP {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise AIImageError("Local AI returned a non-JSON response") from exc
    if not isinstance(payload, dict):
        raise AIImageError("Local AI returned an unexpected response shape")
    return _extract_b64_image(payload)


def _crop_to_largest_face(image_bytes: bytes, faces: list[dict] | None) -> bytes:
    from io import BytesIO

    from PIL import Image

    img = Image.open(BytesIO(image_bytes))
    w, h = img.size
    target_dim = min(w, h)

    cx, cy = w / 2.0, h / 2.0

    if faces:
        largest_face = None
        max_area = -1.0
        for face in faces:
            x1 = face.get("bounding_box_x1")
            y1 = face.get("bounding_box_y1")
            x2 = face.get("bounding_box_x2")
            y2 = face.get("bounding_box_y2")
            if None not in (x1, y1, x2, y2):
                area = (x2 - x1) * (y2 - y1)
                if area > max_area:
                    max_area = area
                    largest_face = face
        if largest_face:
            cx = (largest_face["bounding_box_x1"] + largest_face["bounding_box_x2"]) / 2.0
            cy = (largest_face["bounding_box_y1"] + largest_face["bounding_box_y2"]) / 2.0

    left = int(cx - target_dim / 2.0)
    top = int(cy - target_dim / 2.0)

    left = max(0, min(w - target_dim, left))
    top = max(0, min(h - target_dim, top))

    cropped = img.crop((left, top, left + target_dim, top + target_dim))
    out = BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue()
