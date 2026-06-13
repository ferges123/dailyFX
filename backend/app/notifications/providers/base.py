from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.utils.url_utils import normalize_base_url as _normalize_url


def _normalize_base_url(url: str) -> str:
    """Normalize notification URL with scheme validation."""
    normalized = _normalize_url(url)
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Notification URL must include scheme and host")
    return normalized


def _extract_json_response(response: httpx.Response, provider: str) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ConnectionError(f"{provider} returned a non-JSON response") from exc
    if not isinstance(payload, dict):
        raise ConnectionError(f"{provider} returned an unexpected response body")
    return payload
