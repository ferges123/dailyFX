import os
from pathlib import Path

from _contract_helpers import make_notification_preset_row

from app.immich.client import ImmichPersonFilter
from app.models.effect_preset import EffectPresetModel
from app.models.filter_preset import FilterPresetModel
from app.services.generation.schedule_runs import build_scheduled_run_context

os.environ["APP_ENV"] = "development"
os.environ["APP_SECRET_KEY"] = "test-api-secret"
test_db = Path("/tmp/immich_ai_creator_test_schedule_runs.db")
test_db.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"


def test_build_scheduled_run_context_parses_models():
    filter_preset = FilterPresetModel(
        name="Filter",
        album_ids_json='["album-1"]',
        person_filters_json='[{"personId": "person-1", "mode": "exclude"}]',
        start_date="2026-05-01",
        end_date="2026-05-02",
        media_type="video",
    )
    effect_preset = EffectPresetModel(
        name="Effects",
        groups_json='{"collage": {"enabled": true, "weight": 1}}',
    )
    notif_one = make_notification_preset_row(name="Notif 1", provider="web")
    notif_two = make_notification_preset_row(name="Notif 2", provider="web")

    context = build_scheduled_run_context(
        schedule_id=42,
        album_name="Album",
        filter_preset=filter_preset,
        effect_preset=effect_preset,
        notification_presets=[notif_one, notif_two],
    )

    assert context.schedule_id == 42
    assert context.album_name == "Album"
    assert context.notification_presets == [notif_one, notif_two]
    assert context.effects_config == {"collage": {"enabled": True, "weight": 1}}
    assert context.filters.album_ids == ["album-1"]
    assert context.filters.person_filters == [ImmichPersonFilter(person_id="person-1", mode="exclude")]
    assert context.filters.media_type == "video"
    assert context.filters.taken_after is not None
    assert context.filters.taken_before is not None

    payload = context.to_run_now_task_payload()
    assert payload.schedule_id == 42
    assert payload.album_name == "Album"
    assert payload.notification_preset_ids is None
    assert payload.filters is not None
    assert payload.filters.to_search_filters() == context.filters
