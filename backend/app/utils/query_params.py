from typing import Any
from datetime import date


def query_str(value: Any, default: str) -> str:
    """Extract string from query param with fallback."""
    if isinstance(value, str) and value.strip():
        return value
    return default


def query_int(value: Any, default: int) -> int:
    """Extract int from query param with fallback."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def query_float(value: Any, default: float) -> float:
    """Extract float from query param with fallback."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def query_date(value: Any) -> date | None:
    """Extract date from query param, return None if invalid."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
