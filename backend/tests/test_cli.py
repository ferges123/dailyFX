from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import sqlalchemy as sa
from _contract_helpers import configure_contract_test_db, make_effect_preset_row

from app.cli import _to_iso_timestamp, main
from app.database import SessionLocal, init_db
from app.models.filter_preset import FilterPresetModel
from app.models.generation_history import GenerationHistoryModel
from app.models.notification_preset import NotificationPresetModel
from app.models.schedule import ScheduleModel
from app.services.generation.history import upsert_history_entry

test_db = configure_contract_test_db("cli")


def _setup_cli_db():
    init_db()
    db = SessionLocal()
    db.query(GenerationHistoryModel).delete()
    db.query(NotificationPresetModel).delete()
    db.query(ScheduleModel).delete()
    db.query(FilterPresetModel).delete()
    from app.models.effect_preset import EffectPresetModel

    db.execute(sa.text("DELETE FROM schedule_notification_presets"))
    db.query(EffectPresetModel).delete()
    db.commit()

    filter_preset = FilterPresetModel(
        name="cli-filter",
        album_ids_json="[]",
        person_filters_json="[]",
        media_type="photo",
    )
    effect_preset = make_effect_preset_row(
        name="cli-effect",
        groups_json='{"instafilter": {"enabled": true, "weight": 1, "config": {}}}',
    )
    notification_preset = NotificationPresetModel(name="cli-notif", provider="web")
    db.add_all([filter_preset, effect_preset, notification_preset])
    db.commit()

    schedule = ScheduleModel(
        name="CLI Schedule",
        enabled=True,
        schedule_expr="daily",
        filter_preset_id=filter_preset.id,
        effect_preset_id=effect_preset.id,
        album_name="CLI Album",
    )
    schedule.notification_presets = [notification_preset]
    db.add(schedule)
    db.commit()
    return db, schedule


def test_dailyfx_cli_generate_writes_handoff_manifest(monkeypatch, capsys):
    db, schedule = _setup_cli_db()
    data_dir = Path(os.environ["DATA_DIR"])
    try:
        monkeypatch.setattr(
            "app.cli.get_or_create_settings",
            lambda _db: SimpleNamespace(
                id=1,
                immich_url="https://immich.example.test",
                encrypted_immich_api_key="encrypted",
                debug_mode=False,
                default_ai_provider="none",
                default_ai_model="",
                ai_image_provider="openai",
                ai_image_model="gpt-image-1",
                ai_prompt_enrichment=False,
                ai_photo_selection_enabled=False,
            ),
        )
        monkeypatch.setattr(
            "app.cli.build_immich_client",
            lambda _settings: SimpleNamespace(),
        )

        async def fake_preview_run_now_assets(**_kwargs):
            return SimpleNamespace(items=[object()])

        async def fake_run_generation_cycle(db, settings, task_id, *args, **kwargs):
            output_dir = data_dir / "results"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{task_id}.png"
            output_path.write_bytes(b"fake image")
            upsert_history_entry(
                db,
                task_id,
                generation_type="ai_anime",
                status="PENDING_REVIEW",
                title="Generated Title",
                summary="Generated Summary",
                source_asset_ids='["asset-1"]',
                output_path=str(output_path),
                image_url=f"/api/generation/history/{task_id}/image",
                provider="openai",
                model="gpt-image-1",
                total_token_count=17,
                tags_json='["AI", "Anime"]',
                schedule_id=kwargs.get("schedule_id"),
                album_name=kwargs.get("album_name"),
                output_format="png",
                config_json=json.dumps(
                    {
                        "metadata_provenance": {"source_vision": {"succeeded": True}},
                        "task_trace": [{"stage": "completed", "message": "done"}],
                    }
                ),
            )
            return {"ok": True}

        monkeypatch.setattr("app.cli.preview_run_now_assets", fake_preview_run_now_assets)
        monkeypatch.setattr("app.cli.run_generation_cycle", fake_run_generation_cycle)

        exit_code = main(["generate", "--schedule-id", str(schedule.id), "--handoff-json"])
        captured = capsys.readouterr()

        assert exit_code == 0
        payload = json.loads(captured.out)
        assert payload["task_id"].startswith(f"cli-s{schedule.id}-")
        assert payload["status"] == "PENDING_REVIEW"
        assert payload["image_path"].endswith(".png")
        assert payload["generation_type"] == "ai_anime"
        assert payload["tags"] == ["AI", "Anime"]
        assert payload["source_asset_ids"] == ["asset-1"]
        assert payload["metadata_provenance"]["source_vision"]["succeeded"] is True
        assert payload["task_trace"] == [{"stage": "completed", "message": "done"}]
        assert "DailyFX-generated image" in payload["handoff_prompt"]
    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_dailyfx_cli_generate_missing_schedule_fails(monkeypatch, capsys):
    init_db()
    db = SessionLocal()
    try:
        db.query(GenerationHistoryModel).delete()
        db.query(NotificationPresetModel).delete()
        db.query(ScheduleModel).delete()
        db.query(FilterPresetModel).delete()
        from app.models.effect_preset import EffectPresetModel

        db.execute(sa.text("DELETE FROM schedule_notification_presets"))
        db.query(EffectPresetModel).delete()
        db.commit()

        monkeypatch.setattr(
            "app.cli.get_or_create_settings",
            lambda _db: SimpleNamespace(
                id=1,
                immich_url="https://immich.example.test",
                encrypted_immich_api_key="encrypted",
                debug_mode=False,
                default_ai_provider="none",
                default_ai_model="",
                ai_image_provider="openai",
                ai_image_model="gpt-image-1",
                ai_prompt_enrichment=False,
                ai_photo_selection_enabled=False,
            ),
        )

        exit_code = main(["generate", "--schedule-id", "9999", "--handoff-json"])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "Schedule 9999 not found" in captured.err
    finally:
        db.close()


def test_dailyfx_cli_lists_schedules(capsys):
    db, schedule = _setup_cli_db()
    try:
        from app.cli import main as cli_main

        exit_code = cli_main(["schedules"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "ID\tNAME\tENABLED" in captured.out
        assert f"{schedule.id}\tCLI Schedule\tyes" in captured.out
    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_to_iso_timestamp_handles_strings_and_datetimes():
    assert _to_iso_timestamp("2026-07-05T12:34:56Z") == "2026-07-05T12:34:56+00:00"
    assert (
        _to_iso_timestamp(
            datetime(2026, 7, 5, 12, 34, 56, tzinfo=timezone.utc),
        )
        == "2026-07-05T12:34:56+00:00"
    )
