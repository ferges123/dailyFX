import io
import json
from pathlib import Path

import pytest
from PIL import Image

# Initialize the test DB first before importing any app modules
from _contract_helpers import configure_contract_test_db
test_db = configure_contract_test_db("studio_routes")

from app.database import SessionLocal, init_db
from app.security import require_auth
from fastapi.testclient import TestClient
from app.main import app
from app.models.generation_history import GenerationHistoryModel

from app.services.studio.validation import (
    MAX_STUDIO_UPLOAD_BYTES,
    StudioUploadValidationError,
    validate_studio_image_upload,
)


@pytest.fixture
def authenticated_client():
    app.dependency_overrides[require_auth] = lambda: None
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


def jpeg_upload_bytes() -> bytes:
    image = Image.new("RGB", (80, 60), color=(10, 120, 160))
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def test_studio_preview_requires_auth_when_auth_enabled() -> None:
    client = TestClient(app)
    response = client.post("/api/studio/preview")
    assert response.status_code in {401, 422}


def test_studio_preview_rejects_unknown_effect(authenticated_client: TestClient) -> None:
    response = authenticated_client.post(
        "/api/studio/preview",
        files={"file": ("sample.jpg", jpeg_upload_bytes(), "image/jpeg")},
        data={"effect_id": "does-not-exist", "config": "{}"},
    )
    assert response.status_code == 404
    assert "effect" in response.json()["detail"].lower()


def test_studio_preview_creates_history_entry(authenticated_client: TestClient, db_session) -> None:
    response = authenticated_client.post(
        "/api/studio/preview",
        files={"file": ("sample.jpg", jpeg_upload_bytes(), "image/jpeg")},
        data={"effect_id": "pencil_sketch", "config": "{}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"]
    assert payload["image_url"] == f"/api/generation/history/{payload['task_id']}/image"
    assert payload["history_url"] == f"/history/{payload['task_id']}"

    row = db_session.query(GenerationHistoryModel).filter_by(task_id=payload["task_id"]).one()
    assert row.status == "PENDING_REVIEW"
    assert row.generation_type == "pencil_sketch"
    assert row.output_path
    assert Path(row.output_path).exists()
    assert json.loads(row.source_asset_ids)[0].startswith("studio://")
