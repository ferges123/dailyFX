"""Helpers for keeping credentials out of application logs."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "key",
    "password",
    "secret",
    "token",
    "review_token",
}
_TELEGRAM_BOT_PATH = re.compile(r"(/bot)[^/\s]+", re.IGNORECASE)
_BEARER_TOKEN = re.compile(r"(Bearer\s+)[^\s,;]+", re.IGNORECASE)
_URL = re.compile(r"https?://[^\s,;]+", re.IGNORECASE)


def redact_url(value: str) -> str:
    """Remove credentials from a URL while retaining its useful destination."""
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.scheme or not parts.netloc:
        return value
    query = [
        (key, "[REDACTED]" if key.lower() in _SENSITIVE_QUERY_KEYS else item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
    ]
    netloc = parts.netloc.rsplit("@", 1)[-1]
    path = _TELEGRAM_BOT_PATH.sub(r"\1[REDACTED]", parts.path)
    return urlunsplit((parts.scheme, netloc, path, urlencode(query), ""))


def redact_sensitive(value: object) -> str:
    """Return a log-safe representation of an exception, URL, or message."""
    text = _BEARER_TOKEN.sub(r"\1[REDACTED]", str(value))
    return _URL.sub(lambda match: redact_url(match.group(0)), text)
