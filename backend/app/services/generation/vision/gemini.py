import httpx
import json
import logging
from .base import AIVisionResult, AIVisionError, GEMINI_VISION_MODEL

logger = logging.getLogger(__name__)

async def _analyze_images_with_gemini(
    api_key: str,
    b64_images: list[str],
    prompt: str,
    model: str = GEMINI_VISION_MODEL,
) -> AIVisionResult:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    parts: list[dict[str, object]] = [{"text": prompt}]
    for index, b64_image in enumerate(b64_images, start=1):
        parts.append({"text": f"Candidate {index}"})
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64_image}})
    payload = {"contents": [{"parts": parts}]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            text_response = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text_response.strip().replace("```json", "").replace("```", "").strip())
            return AIVisionResult(
                title=parsed.get("title", "Ranking"),
                summary=json.dumps(parsed),
                provider="gemini",
                model=model,
            )
        except Exception as exc:
            logger.error("Gemini multi-image vision error: %s", exc)
            raise AIVisionError(f"Gemini multi-image analysis failed: {exc}") from exc


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
        "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}}]}]
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
                model=model,
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
        "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}}]}]
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


async def _fuse_gemini(api_key: str, prompt: str, model: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as exc:
            logger.error("Gemini prompt fusion error: %s", exc)
            raise AIVisionError(f"Gemini prompt fusion failed: {exc}") from exc
