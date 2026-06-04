import asyncio
import importlib
import sys
from datetime import datetime, timezone

import pytest
from _contract_helpers import configure_contract_test_db
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api import routes_ai_effects as ai_effects_routes
from app.api import routes_generation as generation_routes
from app.api.routes_ai_effects import (
    create_ai_effect,
    delete_ai_effect,
    export_ai_effects,
    import_ai_effects,
    list_ai_effects,
    reset_ai_effect,
    update_ai_effect,
)
from app.api.routes_generation import list_generation_modules
from app.database import SessionLocal, init_db
from app.models.ai_effect import AIEffectModel
from app.schemas.ai_effects import AIEffectCreate, AIEffectImportItem, AIEffectImportRequest, AIEffectUpdate
from app.security import require_auth
from app.services.generation import ai_effects_seed as seed_module
from app.services.generation.ai_effects import get_seed_dir, load_seed_manifest
from app.services.generation.ai_effects_seed import AIEffectManifest, load_seed_effects
from app.services.generation.bootstrap import bootstrap_builtin_ai_effects
from app.services.generation.modules import MODULES

test_db = configure_contract_test_db("ai_effects")

http_app = FastAPI()
http_app.include_router(ai_effects_routes.router)
http_app.dependency_overrides[require_auth] = lambda: None


def test_ai_effect_modules_import_cleanly():
    modules = [
        "app.services.generation.ai_effects",
        "app.services.generation.ai_effects_seed",
        "app.services.generation.ai_effects_repository",
        "app.services.generation.ai_effects_builder",
        "app.services.generation.ai_effects_sync",
        "app.services.generation.modules",
    ]

    for module_name in modules:
        sys.modules.pop(module_name, None)

    imported = [importlib.import_module(module_name) for module_name in modules]
    assert all(imported)


def test_generation_module_registry_surfaces_repository_errors(monkeypatch):
    from app.services.generation import ai_effects_repository

    MODULES.invalidate()

    def exploding_list(*args, **kwargs):
        raise RuntimeError("repository failed")

    monkeypatch.setattr(ai_effects_repository, "list_ai_effect_rows", exploding_list)

    with pytest.raises(RuntimeError, match="repository failed"):
        MODULES.refresh()


def test_bootstrap_builtin_ai_effects_retries_on_integrity_error(monkeypatch):
    from app.services.generation import ai_effects_sync

    init_db()
    calls = {"count": 0}
    original = ai_effects_sync.sync_builtin_ai_effects

    def flaky_sync(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise IntegrityError("INSERT INTO ai_effects", {}, Exception("duplicate key"))
        return original(*args, **kwargs)

    monkeypatch.setattr(ai_effects_sync, "sync_builtin_ai_effects", flaky_sync)
    bootstrap_builtin_ai_effects()
    assert calls["count"] == 2


def test_bootstrap_builtin_ai_effects_propagates_second_integrity_error(monkeypatch):
    from app.services.generation import ai_effects_sync

    init_db()
    calls = {"count": 0}

    def always_failing_sync(*args, **kwargs):
        calls["count"] += 1
        raise IntegrityError("INSERT INTO ai_effects", {}, Exception("duplicate key"))

    monkeypatch.setattr(ai_effects_sync, "sync_builtin_ai_effects", always_failing_sync)

    with pytest.raises(IntegrityError):
        bootstrap_builtin_ai_effects()

    assert calls["count"] == 2


def test_bootstrap_builtin_ai_effects_propagates_non_integrity_errors(monkeypatch):
    from app.services.generation import ai_effects_sync

    init_db()

    def exploding_sync(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ai_effects_sync, "sync_builtin_ai_effects", exploding_sync)

    with pytest.raises(RuntimeError):
        bootstrap_builtin_ai_effects()


def test_ai_effects_manifest_is_required(tmp_path, monkeypatch):
    seed_dir = tmp_path / "missing_ai_effects_data"
    monkeypatch.setattr(seed_module, "get_seed_dir", lambda: seed_dir)
    monkeypatch.setattr(seed_module, "get_seed_manifest_path", lambda: seed_dir / "manifest.json")

    with pytest.raises(FileNotFoundError):
        load_seed_effects()


def test_ai_effects_manifest_rejects_duplicate_ids(monkeypatch):
    manifest = AIEffectManifest.model_validate(
        {
            "schema_version": 1,
            "effects": [
                {"id": "ai_dup", "display_group": "One"},
                {"id": "ai_dup", "display_group": "Two"},
            ],
        }
    )
    monkeypatch.setattr(seed_module, "load_seed_manifest", lambda: manifest)

    with pytest.raises(ValueError, match="Duplicate AI effect id in manifest"):
        seed_module.get_seed_manifest_entry_map()


def test_ai_effects_manifest_rejects_unknown_schema_version(monkeypatch):
    manifest = AIEffectManifest(schema_version=2, effects=[])
    monkeypatch.setattr(seed_module, "load_seed_manifest", lambda: manifest)

    with pytest.raises(ValueError, match="Unsupported AI effect manifest schema version"):
        load_seed_effects()


def test_builtin_ai_effects_are_seeded_and_listed():
    init_db()
    db = SessionLocal()
    try:
        rows = db.query(AIEffectModel).all()
        assert len(rows) >= 11
        anime = db.get(AIEffectModel, "ai_anime")
        assert anime is not None
        assert anime.title == "AI Anime"
        assert anime.display_group == "Illustration"
        assert anime.enabled is True
        seed_dir = get_seed_dir()
        seed_files = sorted(seed_dir.glob("*.json"))
        manifest = load_seed_manifest()
        assert manifest is not None
        manifest_ids = [entry.id for entry in manifest.effects]
        assert len(seed_files) - 1 == len(manifest_ids)
        assert len(manifest_ids) == len(rows)
        assert all(path.stem == path.stem.lower() for path in seed_files if path.name != "manifest.json")
        assert {path.stem for path in seed_files if path.name != "manifest.json"} == set(manifest_ids)
        listed = list_ai_effects(db)
        assert [item.id for item in listed] == manifest_ids
        assert any(item.id == "ai_anime" for item in listed)
        assert any(item.display_group == "Illustration" for item in listed if item.id == "ai_anime")
        modules = asyncio.run(list_generation_modules())
        assert any(item.name == "ai_anime" for item in modules)
    finally:
        db.close()


def test_hidden_builtins_do_not_hide_custom_overrides(monkeypatch):
    init_db()
    db = SessionLocal()
    try:
        row = db.get(AIEffectModel, "ai_anime")
        assert row is not None
        original_source = row.source
        original_user_modified_at = row.user_modified_at

        row.source = "custom"
        db.commit()
        MODULES.invalidate()
        monkeypatch.setattr(generation_routes, "get_seed_hidden_map", lambda: {"ai_anime": True})
        monkeypatch.setattr(ai_effects_routes, "get_seed_hidden_map", lambda: {"ai_anime": True})

        modules = asyncio.run(list_generation_modules())
        listed = ai_effects_routes.list_ai_effects(db)
        assert any(item.name == "ai_anime" for item in modules)
        assert any(item.id == "ai_anime" for item in listed)
    finally:
        row = db.get(AIEffectModel, "ai_anime")
        if row is not None:
            row.source = original_source
            row.user_modified_at = original_user_modified_at
            db.commit()
            MODULES.invalidate()
        db.close()


def test_ai_effect_crud_and_reset_flow():
    init_db()
    db = SessionLocal()
    try:
        body = AIEffectCreate(
            id="ai_test_custom",
            title="Test Custom",
            description="Custom effect for tests",
            display_group="Custom Group",
            positive_prompt="Turn the image into a test effect.",
            negative_prompt="blurry, low quality",
            custom_prompt_placeholder="e.g. test prompt",
            enabled=True,
        )
        created = create_ai_effect(body, db)
        assert created.id == "ai_test_custom"
        assert created.source == "custom"

        updated = update_ai_effect(
            "ai_test_custom",
            AIEffectUpdate(
                id="ai_test_custom",
                title="Updated Custom",
                description="Updated custom effect",
                display_group="Updated Group",
                positive_prompt="Updated prompt",
                negative_prompt="noisy",
                custom_prompt_placeholder="e.g. updated",
                enabled=False,
            ),
            db,
        )
        assert updated.title == "Updated Custom"
        assert updated.display_group == "Updated Group"
        assert updated.enabled is False

        deleted = delete_ai_effect("ai_test_custom", db)
        assert deleted.id == "ai_test_custom"
        assert db.get(AIEffectModel, "ai_test_custom") is None

        anime_before = db.get(AIEffectModel, "ai_anime")
        assert anime_before is not None
        anime_before.title = "Locally Modified Anime"
        anime_before.display_group = "Local Group"
        anime_before.user_modified_at = datetime.now(timezone.utc)
        db.commit()

        reset = reset_ai_effect("ai_anime", db)
        assert reset.id == "ai_anime"
        assert reset.title == "AI Anime"
        assert reset.display_group == "Illustration"
        assert reset.user_modified_at is None
    finally:
        db.close()


def test_ai_effect_import_overwrite_clears_builtin_hashes():
    init_db()
    db = SessionLocal()
    try:
        row_before = db.get(AIEffectModel, "ai_anime")
        assert row_before is not None
        assert row_before.source == "builtin"
        assert row_before.builtin_hash is not None

        overwritten = import_ai_effects(
            AIEffectImportRequest(
                overwrite_existing=True,
                effects=[
                    AIEffectImportItem(
                        id="ai_anime",
                        title="AI Anime Imported",
                        description="Overwritten via import",
                        display_group="Imported Group",
                        positive_prompt="Imported prompt",
                        negative_prompt="avoid artifacts",
                        custom_prompt_placeholder="e.g. imported",
                        enabled=False,
                        source="custom",
                    )
                ],
            ),
            db,
        )

        assert overwritten.updated == ["ai_anime"]

        row_after = db.get(AIEffectModel, "ai_anime")
        assert row_after is not None
        assert row_after.source == "custom"
        assert row_after.builtin_hash is None
        assert row_after.latest_builtin_hash is None
        assert row_after.user_modified_at is None
    finally:
        db.close()


def test_ai_effect_import_and_export_flow():
    init_db()
    db = SessionLocal()
    try:
        import_body = AIEffectImportRequest(
            overwrite_existing=False,
            effects=[
                AIEffectImportItem(
                    id="ai_imported_test",
                    title="Imported Test",
                    description="Imported effect for export coverage",
                    display_group="Imported Group",
                    positive_prompt="Import the image into a test effect.",
                    negative_prompt="low quality",
                    custom_prompt_placeholder="e.g. imported prompt",
                    enabled=True,
                    source="imported",
                )
            ],
        )
        imported = import_ai_effects(import_body, db)
        assert imported.added == ["ai_imported_test"]
        assert imported.updated == []
        assert imported.conflicts == []

        row = db.get(AIEffectModel, "ai_imported_test")
        assert row is not None
        assert row.source == "imported"

        exported = export_ai_effects(db)
        exported_ids = [item.id for item in exported.effects]
        assert exported.schema_version == 1
        assert "ai_imported_test" in exported_ids

        conflict = import_ai_effects(import_body, db)
        assert conflict.added == []
        assert conflict.updated == []
        assert conflict.conflicts == ["ai_imported_test"]

        overwrite_body = AIEffectImportRequest(
            overwrite_existing=True,
            effects=[
                AIEffectImportItem(
                    id="ai_imported_test",
                    title="Imported Test Updated",
                    description="Updated imported effect",
                    display_group="Imported Group",
                    positive_prompt="Updated prompt",
                    negative_prompt="washed out",
                    custom_prompt_placeholder="e.g. updated imported prompt",
                    enabled=False,
                    source="custom",
                )
            ],
        )
        overwritten = import_ai_effects(overwrite_body, db)
        assert overwritten.added == []
        assert overwritten.conflicts == []
        assert overwritten.updated == ["ai_imported_test"]

        row_after = db.get(AIEffectModel, "ai_imported_test")
        assert row_after is not None
        assert row_after.title == "Imported Test Updated"
        assert row_after.enabled is False
        assert row_after.source == "custom"
    finally:
        db.close()


def test_ai_effect_import_and_export_http_roundtrip():
    try:
        with TestClient(http_app) as client:
            import_response = client.post(
                "/api/ai-effects/import",
                json={
                    "schema_version": 1,
                    "overwrite_existing": False,
                    "effects": [
                        {
                            "id": "ai_http_imported_test",
                            "title": "HTTP Imported Test",
                            "description": "Imported over HTTP",
                            "display_group": "HTTP Group",
                            "positive_prompt": "Import via HTTP.",
                            "negative_prompt": "washed out",
                            "custom_prompt_placeholder": "e.g. http prompt",
                            "enabled": True,
                            "source": "imported",
                        }
                    ],
                },
            )
            assert import_response.status_code == 200
            payload = import_response.json()
            assert payload["added"] == ["ai_http_imported_test"]
            assert payload["updated"] == []
            assert payload["conflicts"] == []

            export_response = client.get("/api/ai-effects/export")
            assert export_response.status_code == 200
            export_payload = export_response.json()
            exported_ids = [item["id"] for item in export_payload["effects"]]
            assert export_payload["schema_version"] == 1
            assert "ai_http_imported_test" in exported_ids

            conflict_response = client.post(
                "/api/ai-effects/import",
                json={
                    "schema_version": 1,
                    "overwrite_existing": False,
                    "effects": [
                        {
                            "id": "ai_http_imported_test",
                            "title": "HTTP Imported Test",
                            "description": "Imported over HTTP",
                            "display_group": "HTTP Group",
                            "positive_prompt": "Import via HTTP.",
                            "negative_prompt": "washed out",
                            "custom_prompt_placeholder": "e.g. http prompt",
                            "enabled": True,
                            "source": "imported",
                        }
                    ],
                },
            )
            assert conflict_response.status_code == 200
            conflict_payload = conflict_response.json()
            assert conflict_payload["added"] == []
            assert conflict_payload["updated"] == []
            assert conflict_payload["conflicts"] == ["ai_http_imported_test"]
    finally:
        http_app.dependency_overrides.clear()
        http_app.dependency_overrides[require_auth] = lambda: None
