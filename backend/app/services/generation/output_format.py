from __future__ import annotations

OutputFormat = str

SUPPORTED_OUTPUT_FORMATS = {"png", "gif", "webp"}
OUTPUT_MIME_TYPES = {
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def normalize_output_format(value: str | None) -> OutputFormat:
    normalized = (value or "png").strip().lower()
    if not normalized:
        return "png"
    if normalized not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format: {value}")
    return normalized


def output_extension(value: str | None) -> str:
    return normalize_output_format(value)


def output_mime_type(value: str | None) -> str:
    return OUTPUT_MIME_TYPES[normalize_output_format(value)]


def is_animated_output(value: str | None) -> bool:
    return normalize_output_format(value) in {"gif", "webp"}
