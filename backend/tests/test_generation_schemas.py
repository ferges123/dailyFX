from datetime import datetime, timezone

from app.schemas.generation import GenerationHistoryResponse


def make_response(image_url: str) -> GenerationHistoryResponse:
    return GenerationHistoryResponse.model_validate(
        {
            "id": 1,
            "task_id": "task-1",
            "generation_type": "test",
            "title": "Test",
            "summary": "Test",
            "source_asset_ids": "[]",
            "config_json": "{}",
            "image_url": image_url,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
        }
    )


def test_cache_buster_preserves_existing_query_parameters():
    response = make_response("/image?thumbnail=true#preview")

    assert response.image_url == "/image?thumbnail=true&t=1767312000#preview"


def test_cache_buster_is_not_duplicated():
    response = make_response("/image?t=123&thumbnail=true")

    assert response.image_url == "/image?t=123&thumbnail=true"
