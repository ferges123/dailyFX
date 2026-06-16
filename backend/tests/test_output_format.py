import pytest

from app.services.generation.output_format import (
    normalize_output_format,
    output_extension,
    output_mime_type,
)


def test_normalize_output_format_defaults_to_png():
    assert normalize_output_format(None) == "png"
    assert normalize_output_format("") == "png"
    assert normalize_output_format("PNG") == "png"


def test_normalize_output_format_accepts_supported_animated_formats():
    assert normalize_output_format("gif") == "gif"
    assert normalize_output_format("WEBP") == "webp"


def test_normalize_output_format_rejects_unknown_format():
    with pytest.raises(ValueError, match="Unsupported output format"):
        normalize_output_format("jpg")


def test_output_extension_and_mime_type():
    assert output_extension("png") == "png"
    assert output_extension("gif") == "gif"
    assert output_extension("webp") == "webp"
    assert output_mime_type("png") == "image/png"
    assert output_mime_type("gif") == "image/gif"
    assert output_mime_type("webp") == "image/webp"
