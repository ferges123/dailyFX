from datetime import date


def parse_date(value: str | None) -> date | None:
    """Parse ISO date string, return None if invalid."""
    if not value or not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
