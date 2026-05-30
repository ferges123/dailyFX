from urllib.parse import urlparse


def normalize_base_url(url: str) -> str:
    """Normalize URL by stripping whitespace and trailing slashes."""
    return url.strip().rstrip("/")


def validate_http_url(url: str, field_name: str) -> str:
    """Validate that a URL is an absolute http(s) URL and return the normalized form."""
    normalized = normalize_base_url(url)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be an absolute http:// or https:// URL")
    return normalized


def normalize_api_url(server_url: str) -> str:
    """Normalize Immich API URL, ensuring /api suffix."""
    stripped = normalize_base_url(server_url)
    if stripped.endswith("/api"):
        return stripped
    return f"{stripped}/api"
