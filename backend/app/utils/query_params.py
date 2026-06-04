from datetime import date
from typing import Any


def query_date(value: Any) -> date | None:
    """Extract date from query param, return None if invalid."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
