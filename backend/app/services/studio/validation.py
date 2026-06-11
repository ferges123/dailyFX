from __future__ import annotations

import mimetypes
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

MAX_STUDIO_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_STUDIO_IMAGE_PIXELS = 50_000_000

ALLOWED_STUDIO_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heic",
}


class StudioUploadValidationError(ValueError):
    pass


@dataclass(frozen=True)
class StudioValidatedUpload:
    extension: str
    mime_type: str
    width: int | None
    height: int | None


def _mime_from_filename(filename: str) -> str | None:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed


def validate_studio_image_upload(*, filename: str, content_type: str | None, content: bytes) -> StudioValidatedUpload:
    if not content:
        raise StudioUploadValidationError("Uploaded file is empty")
    if len(content) > MAX_STUDIO_UPLOAD_BYTES:
        raise StudioUploadValidationError("Studio uploads are limited to 25 MB")

    normalized_type = (content_type or _mime_from_filename(filename) or "").split(";")[0].strip().lower()
    extension = ALLOWED_STUDIO_TYPES.get(normalized_type)
    if extension is None:
        raise StudioUploadValidationError("Unsupported Studio image format. Use PNG, JPG, GIF, or HEIC.")

    if extension == ".heic":
        try:
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
        except Exception as exc:
            raise StudioUploadValidationError(
                "HEIC upload is allowed, but this server cannot decode this HEIC file."
            ) from exc
    else:
        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
        except Exception as exc:
            raise StudioUploadValidationError("Uploaded file is not a valid image") from exc

    if width * height > MAX_STUDIO_IMAGE_PIXELS:
        raise StudioUploadValidationError("Studio images are limited to 50 megapixels")

    return StudioValidatedUpload(extension=extension, mime_type=normalized_type, width=width, height=height)


def create_studio_session_dir(temp_root: Path) -> tuple[str, Path]:
    session_id = uuid.uuid4().hex
    session_dir = temp_root / session_id
    session_dir.mkdir(parents=True, exist_ok=False)
    return session_id, session_dir
