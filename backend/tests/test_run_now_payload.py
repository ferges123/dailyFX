import os
from pathlib import Path

os.environ["APP_ENV"] = "development"
os.environ["APP_SECRET_KEY"] = "test-api-secret"
test_db = Path("/tmp/immich_ai_creator_test_run_now_payload.db")
test_db.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"

from app.immich.client import ImmichPersonFilter, ImmichSearchFilters
from app.services.generation.run_now import (
    build_run_now_search_filters,
    build_run_now_task_payload,
    parse_run_now_task_payload,
)


def test_run_now_search_filters_accept_personId_aliases():
    filters = build_run_now_search_filters(
        album_ids=["album-1"],
        person_filters=[{"personId": "person-1", "mode": "exclude"}],
        start_date="2026-05-01",
        end_date="2026-05-02",
        media_type="video",
    )

    assert filters.album_ids == ["album-1"]
    assert filters.person_filters == [ImmichPersonFilter(person_id="person-1", mode="exclude")]
    assert filters.media_type == "video"
    assert filters.taken_after is not None
    assert filters.taken_before is not None


def test_run_now_task_payload_round_trip_preserves_fields():
    filters = ImmichSearchFilters(
        album_ids=["album-1"],
        person_filters=[ImmichPersonFilter(person_id="person-1", mode="obligatory")],
        taken_after=None,
        taken_before=None,
        media_type="all",
    )

    payload = build_run_now_task_payload(
        filters=filters,
        effects_config={"collage": {"enabled": True, "weight": 1}},
        selected_asset_ids=["asset-1", "asset-2"],
        schedule_id=7,
        album_name="Album",
        notification_preset_ids=[1, 2],
    )

    parsed = parse_run_now_task_payload(payload.to_json())

    assert parsed.schedule_id == 7
    assert parsed.album_name == "Album"
    assert parsed.notification_preset_ids == [1, 2]
    assert parsed.selected_asset_ids == ["asset-1", "asset-2"]
    assert parsed.effects_config == {"collage": {"enabled": True, "weight": 1}}
    assert parsed.filters is not None
    assert parsed.filters.to_search_filters() == filters
    assert payload.to_run_generation_kwargs(notification_presets=["np-1"]) == {
        "filters": filters,
        "effects_config": {"collage": {"enabled": True, "weight": 1}},
        "selected_asset_ids": ["asset-1", "asset-2"],
        "schedule_id": 7,
        "album_name": "Album",
        "notification_presets": ["np-1"],
    }
