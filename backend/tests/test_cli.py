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
        assert payload["task_id"].startswith("man-")
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


def test_dailyfx_cli_finalize_host_requires_updated_metadata(tmp_path, capsys):
    db, schedule = _setup_cli_db()
    try:
        from app.services.generation.history import upsert_history_entry

        task_id = "cli-s1-abc123"
        upsert_history_entry(
            db,
            task_id,
            title="Original Title",
            summary="Original Summary",
            source_asset_ids='["asset-1"]',
            generation_type="ai_claymation",
        )

        output_path = tmp_path / "result.png"
        output_path.write_bytes(b"image")
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "schedule_id": schedule.id,
                    "target": "agy",
                    "generation_type": "ai_claymation",
                    "title": "Miniature Family Stroll",
                    "summary": "Use the image.",
                    "tags": ["family", "portrait", "claymation"],
                    "output_path": str(output_path),
                    "source_asset_id": "asset-1",
                    "config_json": {},
                }
            ),
            encoding="utf-8",
        )

        exit_code = main(["finalize-host", "--manifest-path", str(manifest_path)])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "metadata_source" in captured.err
    finally:
        db.close()
        test_db.unlink(missing_ok=True)


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


def test_dailyfx_cli_finalize_host_rejects_unchanged_metadata(tmp_path, capsys):
    db, schedule = _setup_cli_db()
    try:
        from app.cli import main as cli_main
        from app.services.generation.history import upsert_history_entry

        # Create a history entry with original metadata
        task_id = "cli-s1-testtask"
        upsert_history_entry(
            db,
            task_id,
            title="Original Title",
            summary="Original Summary",
            tags_json=json.dumps(["tag1", "tag2", "tag3"]),
            source_asset_ids='["asset-1"]',
            generation_type="instafilter",
        )

        output_path = tmp_path / "result.png"
        output_path.write_bytes(b"image")

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "schedule_id": schedule.id,
                    "target": "agy",
                    "generation_type": "instafilter",
                    "title": "Original Title",  # Unchanged!
                    "summary": "Original Summary",  # Unchanged!
                    "tags": ["tag1", "tag2", "tag3"],
                    "metadata_source": "host_agent_final_vision",
                    "output_path": str(output_path),
                    "source_asset_id": "asset-1",
                }
            ),
            encoding="utf-8",
        )

        exit_code = cli_main(["finalize-host", "--manifest-path", str(manifest_path)])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "did not update title, summary, or tags" in captured.err
    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_host_render_paths_resolves_correctly():
    from app.cli import _host_render_paths

    source_path, output_path = _host_render_paths("test-task-123")
    assert source_path.name == "test-task-123.input.png"
    assert output_path.name == "test-task-123.png"


def test_prepare_host_render_sets_failed_status_on_exception(monkeypatch):
    import asyncio

    import pytest

    db, schedule = _setup_cli_db()
    try:
        from app.cli import CLIError, _prepare_host_render
        from app.services.generation.tasks import get_task

        # Force a failure during planning
        monkeypatch.setattr(
            "app.services.generation.pipeline.planning._pipeline_setup_and_planning",
            lambda ctx: None,  # trigger CLIError "Unable to prepare host render..."
        )

        with pytest.raises(CLIError):
            asyncio.run(_prepare_host_render(schedule.id, "fail-task-1", "agy"))

        task = get_task(db, "fail-task-1")
        assert task is not None
        assert task.status == "failed"
        assert "Unable to prepare host render" in task.error
    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_generate_sets_failed_status_on_exception(monkeypatch):
    import asyncio

    import pytest

    db, schedule = _setup_cli_db()
    try:
        from app.cli import _generate
        from app.services.generation.tasks import get_task

        # Mock settings and client to get past init phase
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

        # Force preview_run_now_assets to raise exception
        async def mock_preview_failed(**kwargs):
            raise Exception("Mocked preview failure")

        monkeypatch.setattr("app.cli.preview_run_now_assets", mock_preview_failed)

        with pytest.raises(Exception) as excinfo:
            asyncio.run(_generate(schedule.id, "fail-task-2"))

        assert "Mocked preview failure" in str(excinfo.value)
        task = get_task(db, "fail-task-2")
        assert task is not None
        assert task.status == "failed"
        assert "Mocked preview failure" in task.error
    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_cli_prevents_duplicate_active_task(monkeypatch):
    import asyncio

    import pytest

    from app.cli import CLIError, _generate, _prepare_host_render
    from app.services.generation.tasks import ensure_task

    db, schedule = _setup_cli_db()
    try:
        # Create an existing queued task in the database
        task_id = "dup-task-1"
        ensure_task(db, task_id, status="queued", schedule_id=schedule.id)

        # 1. Test prepare_host_render rejects enqueuing a queued task
        with pytest.raises(CLIError) as excinfo:
            asyncio.run(_prepare_host_render(schedule.id, task_id, "agy"))
        assert f"Task {task_id} is already in state queued" in str(excinfo.value)

        # Change status to running
        ensure_task(db, task_id, status="running", schedule_id=schedule.id)

        # 2. Test prepare_host_render rejects enqueuing a running task
        with pytest.raises(CLIError) as excinfo:
            asyncio.run(_prepare_host_render(schedule.id, task_id, "agy"))
        assert f"Task {task_id} is already in state running" in str(excinfo.value)

        # 3. Test generate rejects enqueuing a running task
        with pytest.raises(CLIError) as excinfo:
            asyncio.run(_generate(schedule.id, task_id))
        assert f"Task {task_id} is already in state running" in str(excinfo.value)

    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_cli_prevents_duplicate_active_task_with_different_task_id(monkeypatch):
    import asyncio

    import pytest

    from app.cli import CLIError, _generate
    from app.services.generation.tasks import ensure_task

    db, schedule = _setup_cli_db()
    try:
        # Create an existing running task in the database for our schedule
        task_id_1 = "dup-task-1"
        ensure_task(db, task_id_1, status="running", schedule_id=schedule.id)

        # Test _generate rejects running with a different task_id
        task_id_2 = "dup-task-2"
        with pytest.raises(CLIError) as excinfo:
            asyncio.run(_generate(schedule.id, task_id_2))
        assert f"Schedule {schedule.id} is already being processed by task {task_id_1}" in str(excinfo.value)
    finally:
        db.close()
        test_db.unlink(missing_ok=True)
