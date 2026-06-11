from pathlib import Path

import pytest
from PIL import Image

from app.services.studio.validation import (
    MAX_STUDIO_UPLOAD_BYTES,
    StudioUploadValidationError,
    validate_studio_image_upload,
)


def write_image(path: Path, fmt: str = "JPEG") -> bytes:
    image = Image.new("RGB", (64, 48), color=(120, 40, 90))
    image.save(path, format=fmt)
    return path.read_bytes()


def test_validate_studio_image_upload_accepts_jpeg(tmp_path: Path) -> None:
    path = tmp_path / "sample.jpg"
    content = write_image(path, "JPEG")

    result = validate_studio_image_upload(
        filename="sample.jpg",
        content_type="image/jpeg",
        content=content,
    )

    assert result.extension == ".jpg"
    assert result.mime_type == "image/jpeg"


def test_validate_studio_image_upload_rejects_large_file() -> None:
    content = b"x" * (MAX_STUDIO_UPLOAD_BYTES + 1)

    with pytest.raises(StudioUploadValidationError, match="25 MB"):
        validate_studio_image_upload(
            filename="large.jpg",
            content_type="image/jpeg",
            content=content,
        )


def test_validate_studio_image_upload_rejects_unsupported_type() -> None:
    with pytest.raises(StudioUploadValidationError, match="Unsupported"):
        validate_studio_image_upload(
            filename="sample.webp",
            content_type="image/webp",
            content=b"not-an-image",
        )


def test_validate_studio_image_upload_rejects_invalid_image_bytes() -> None:
    with pytest.raises(StudioUploadValidationError, match="valid image"):
        validate_studio_image_upload(
            filename="sample.jpg",
            content_type="image/jpeg",
            content=b"not-an-image",
        )
