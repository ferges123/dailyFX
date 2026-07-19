import re


def parse_duration_to_seconds(value: str | int) -> int:
    """Parse a duration string (e.g. '7d', '12h', '30m', '60s') or integer representing seconds

    into an integer number of seconds.
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip().lower()
        if not value:
            return 0
        if value.isdigit():
            return int(value)

        # Matches formats like "7d", "12h", "30m", "60s", "1w"
        match = re.match(r"^(\d+)([dhmsw]?)$", value)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit == "d":
                return amount * 86400
            elif unit == "h":
                return amount * 3600
            elif unit == "m":
                return amount * 60
            elif unit == "s" or not unit:
                return amount
            elif unit == "w":
                return amount * 604800
        raise ValueError(f"Invalid duration format: '{value}'")
    return int(value)
