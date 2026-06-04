import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from _contract_helpers import configure_contract_test_db, make_effect_preset_row

from app.database import SessionLocal
from app.database import init_db as _init_db
from app.immich.client import ImmichSearchFilters
from app.models.filter_preset import FilterPresetModel
from app.models.generation_history import GenerationHistoryModel
from app.models.schedule import ScheduleModel
from app.services.generation.ai_vision import AIVisionResult
from app.services.generation.engine import _merge_module_defaults, run_generation_cycle
from app.services.immich import get_or_create_settings

test_db = configure_contract_test_db("engine")


def init_db():
    _init_db()


def _make_fake_asset(asset_id="asset-1", filename="photo.jpg"):
    asset = MagicMock()
    asset.id = asset_id
    asset.original_file_name = filename
    asset.created_at = "2024-06-15T10:30:00.000Z"
    return asset


def _make_fake_page(assets):
    page = MagicMock()
    page.items = assets
    return page


def _fake_image_bytes() -> bytes:
    from io import BytesIO

    from PIL import Image

    img = Image.new("RGB", (100, 100), color=(128, 64, 32))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _fake_image_bytes_color(color: tuple[int, int, int]) -> bytes:
    from io import BytesIO

    from PIL import Image

    img = Image.new("RGB", (100, 100), color=color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _setup_db():
    import app.database as database

    if database.engine is not None:
        database.engine.dispose()
    database.engine = None
    database._current_database_url = None
    test_db.unlink(missing_ok=True)
    init_db()
    return SessionLocal()


def _get_test_filters():
    return ImmichSearchFilters(album_ids=None, person_filters=[])


def _create_ai_vision_schedule(
    db,
    *,
    suffix: str,
    groups_json: str,
    media_type: str = "photo",
) -> None:
    filter_preset = FilterPresetModel(
        name=f"test-filter-preset-{suffix}",
        album_ids_json="[]",
        person_filters_json="[]",
        media_type=media_type,
    )
    effect_preset = make_effect_preset_row(
        name=f"test-effect-preset-{suffix}",
        groups_json=groups_json,
    )
    db.add_all([filter_preset, effect_preset])
    db.commit()

    schedule = ScheduleModel(
        name=f"test-schedule-{suffix}",
        enabled=True,
        schedule_expr="weekly",
        filter_preset_id=filter_preset.id,
        effect_preset_id=effect_preset.id,
        album_name="AI Photos",
        ai_vision_provider="openai",
        ai_vision_model="gpt-4o-mini",
        ai_image_provider="openai",
        ai_image_model="gpt-image-1",
        ai_prompt_enrichment=False,
    )
    db.add(schedule)
    db.commit()


# ── tests ─────────────────────────────────────────────────────────────────────


def test_run_generation_cycle_no_groups():
    db = _setup_db()
    try:
        row = get_or_create_settings(db)
        db.commit()

        # No effects_config passed -> returns None
        result = asyncio.run(
            run_generation_cycle(db, row, "task-nogroups", force=True, effects_config=None, filters=_get_test_filters())
        )
        assert result is None
    finally:
        db.close()


def test_run_generation_cycle_no_active_groups():
    db = _setup_db()
    try:
        row = get_or_create_settings(db)
        db.commit()

        effects_config = {
            "instafilter": {"enabled": False, "weight": 1, "config": {}},
            "ai_caricature": {"enabled": False, "weight": 1, "config": {}},
            "ai_anime": {"enabled": False, "weight": 1, "config": {}},
            "ai_cinematic_3d_toy": {"enabled": False, "weight": 1, "config": {}},
            "ai_collectible_figure": {"enabled": False, "weight": 1, "config": {}},
            "ai_fantasy_hero": {"enabled": False, "weight": 1, "config": {}},
            "ai_high_fashion_editorial": {"enabled": False, "weight": 1, "config": {}},
            "ai_brick_built_figure": {"enabled": False, "weight": 1, "config": {}},
            "ai_yellow_cartoon_sitcom": {"enabled": False, "weight": 1, "config": {}},
        }
        result = asyncio.run(
            run_generation_cycle(
                db, row, "task-inactive", force=True, effects_config=effects_config, filters=_get_test_filters()
            )
        )
        assert result is None
    finally:
        db.close()


def test_merge_module_defaults_adds_new_ai_modules():
    merged = _merge_module_defaults({"instafilter": {"enabled": True, "weight": 3, "config": {"styles": ["aden"]}}})
    assert "ai_caricature" in merged
    assert "ai_anime" in merged
    assert "ai_cinematic_3d_toy" in merged
    assert "ai_collectible_figure" in merged
    assert "ai_fantasy_hero" in merged
    assert "ai_high_fashion_editorial" in merged
    assert "ai_brick_built_figure" in merged
    assert "ai_yellow_cartoon_sitcom" in merged
    assert merged["instafilter"]["weight"] == 3
    # Merged defaults from preset: modules NOT present in input are disabled
    assert merged["ai_caricature"]["enabled"] is False


def test_run_generation_cycle_no_assets():
    db = _setup_db()
    try:
        row = get_or_create_settings(db)
        db.commit()

        fake_client = AsyncMock()
        fake_client.search_assets = AsyncMock(return_value=_make_fake_page([]))

        effects_config = {"instafilter": {"enabled": True, "weight": 1, "config": {}}}

        with patch("app.services.generation.engine.build_immich_client", return_value=fake_client):
            result = asyncio.run(
                run_generation_cycle(
                    db, row, "task-noassets", force=True, effects_config=effects_config, filters=_get_test_filters()
                )
            )

        assert result is None
    finally:
        db.close()


def test_run_generation_cycle_instafilter(tmp_path):
    db = _setup_db()
    try:
        row = get_or_create_settings(db)
        db.commit()

        fake_client = AsyncMock()
        fake_client.search_assets = AsyncMock(return_value=_make_fake_page([_make_fake_asset()]))
        fake_client.get_asset_data = AsyncMock(return_value=_fake_image_bytes())
        fake_client.get_asset_exif = AsyncMock(
            return_value={"make": "Canon", "model": "EOS R5", "latitude": 52.2, "longitude": 21.0}
        )

        effects_config = {"instafilter": {"enabled": True, "weight": 1, "config": {"styles": ["aden"]}}}

        with (
            patch("app.services.generation.engine.build_immich_client", return_value=fake_client),
            patch("app.services.generation.engine.get_settings") as mock_cfg,
            patch("app.services.generation.engine._send_gen_notification", new=AsyncMock()),
            patch(
                "app.services.generation.engine.random.choices",
                return_value=[("instafilter", {"enabled": True, "weight": 1, "config": {"styles": ["aden"]}})],
            ),
        ):
            mock_cfg.return_value.data_dir = tmp_path
            result = asyncio.run(
                run_generation_cycle(
                    db, row, "task-instafilter", force=True, effects_config=effects_config, filters=_get_test_filters()
                )
            )

        assert result is not None
        assert result["type"] == "instafilter"
        assert result["task_id"] == "task-instafilter"

        entry = db.query(GenerationHistoryModel).filter_by(task_id="task-instafilter").first()
        assert entry is not None
        assert entry.generation_type == "instafilter"
        assert entry.status == "PENDING_REVIEW"
        assert Path(entry.output_path).exists()
    finally:
        db.close()


def test_run_generation_cycle_requested_module_and_selected_assets(tmp_path):
    db = _setup_db()
    try:
        row = get_or_create_settings(db)
        db.commit()

        asset_a = _make_fake_asset("asset-a")
        asset_b = _make_fake_asset("asset-b")
        fake_client = AsyncMock()
        fake_client.search_assets = AsyncMock(return_value=_make_fake_page([asset_a, asset_b]))
        fake_client.get_asset_data = AsyncMock(return_value=_fake_image_bytes())
        fake_client.get_asset_exif = AsyncMock(return_value={})

        effects_config = {
            "instafilter": {"enabled": True, "weight": 1, "config": {"styles": ["aden"]}},
            "glitch": {"enabled": True, "weight": 1, "config": {}},
        }

        with (
            patch("app.services.generation.engine.build_immich_client", return_value=fake_client),
            patch("app.services.generation.engine.get_settings") as mock_cfg,
            patch("app.services.generation.engine._send_gen_notification", new=AsyncMock()),
            patch(
                "app.services.generation.engine.random.choices",
                return_value=[("glitch", {"enabled": True, "weight": 1, "config": {}})],
            ),
        ):
            mock_cfg.return_value.data_dir = tmp_path
            result = asyncio.run(
                run_generation_cycle(
                    db,
                    row,
                    "task-requested-module",
                    force=True,
                    effects_config=effects_config,
                    filters=_get_test_filters(),
                    selected_asset_ids=["asset-b"],
                )
            )

        assert result is not None
        assert result["type"] == "glitch"
        fake_client.get_asset_data.assert_awaited()
        called_asset_id = fake_client.get_asset_data.await_args.args[0]
        assert called_asset_id == "asset-b"
    finally:
        db.close()


def test_run_generation_cycle_saves_failed_on_error(tmp_path):
    db = _setup_db()
    try:
        row = get_or_create_settings(db)
        db.commit()

        fake_client = AsyncMock()
        fake_client.search_assets = AsyncMock(return_value=_make_fake_page([_make_fake_asset()]))
        fake_client.get_asset_data = AsyncMock(side_effect=RuntimeError("network error"))

        effects_config = {"instafilter": {"enabled": True, "weight": 1, "config": {"styles": ["aden"]}}}

        with (
            patch("app.services.generation.engine.build_immich_client", return_value=fake_client),
            patch("app.services.generation.engine.get_settings") as mock_cfg,
        ):
            mock_cfg.return_value.data_dir = tmp_path
            result = asyncio.run(
                run_generation_cycle(
                    db, row, "task-failed", force=True, effects_config=effects_config, filters=_get_test_filters()
                )
            )

        assert result is None

        entry = db.query(GenerationHistoryModel).filter_by(task_id="task-failed").first()
        assert entry is not None
        assert entry.status == "FAILED"
        assert "network error" in entry.summary
    finally:
        db.close()


def test_run_generation_cycle_collage(tmp_path):
    db = _setup_db()
    try:
        row = get_or_create_settings(db)
        db.commit()

        fake_client = AsyncMock()
        fake_client.search_assets = AsyncMock(return_value=_make_fake_page([_make_fake_asset()]))
        fake_client.get_asset_data = AsyncMock(return_value=_fake_image_bytes())
        fake_client.get_asset_exif = AsyncMock(return_value={"make": "Sony", "model": "A7", "iso": 400})

        effects_config = {
            "collage": {"enabled": True, "weight": 1, "config": {"styles": ["aden", "moon", "lark", "lofi"]}}
        }

        with (
            patch("app.services.generation.engine.build_immich_client", return_value=fake_client),
            patch("app.services.generation.engine.get_settings") as mock_cfg,
            patch("app.services.generation.engine._send_gen_notification", new=AsyncMock()),
            patch(
                "app.services.generation.engine.random.choices",
                return_value=[
                    ("collage", {"enabled": True, "weight": 1, "config": {"styles": ["aden", "moon", "lark", "lofi"]}})
                ],
            ),
        ):
            mock_cfg.return_value.data_dir = tmp_path
            result = asyncio.run(
                run_generation_cycle(
                    db, row, "task-collage", force=True, effects_config=effects_config, filters=_get_test_filters()
                )
            )

        assert result is not None
        assert result["type"] == "collage"
        assert len(result["styles"]) == 4

        entry = db.query(GenerationHistoryModel).filter_by(task_id="task-collage").first()
        assert entry is not None
        assert entry.generation_type == "collage"
        assert entry.status == "PENDING_REVIEW"
        assert Path(entry.output_path).exists()
    finally:
        db.close()


def test_effect_preset_random_selection():
    import random
    from collections import Counter

    # Simulate a preset with 11 active AI modules, all with weight=1
    active_groups = [
        ("ai_anime", {"enabled": True, "weight": 1}),
        ("ai_caricature", {"enabled": True, "weight": 1}),
        ("ai_claymation", {"enabled": True, "weight": 1}),
        ("ai_comic_book", {"enabled": True, "weight": 1}),
        ("ai_cinematic_3d_toy", {"enabled": True, "weight": 1}),
        ("ai_fantasy_hero", {"enabled": True, "weight": 1}),
        ("ai_cyberpunk", {"enabled": True, "weight": 1}),
        ("ai_yellow_cartoon_sitcom", {"enabled": True, "weight": 1}),
        ("ai_high_fashion_editorial", {"enabled": True, "weight": 1}),
        ("ai_collectible_figure", {"enabled": True, "weight": 1}),
        ("ai_brick_built_figure", {"enabled": True, "weight": 1}),
    ]

    weights = [data.get("weight", 1) for _, data in active_groups]
    selections = []
    # Perform 100 choices
    for _ in range(100):
        selected_name, _ = random.choices(active_groups, weights=weights, k=1)[0]
        selections.append(selected_name)

    counts = Counter(selections)
    # Check that it is indeed randomized (at least 5 unique modules selected out of 11)
    assert len(counts) >= 5
    # Every active module should have a non-zero chance, check that at least some are selected multiple times
    assert any(count > 1 for count in counts.values())


def test_ai_module_tags_injection(tmp_path):
    db = _setup_db()
    try:
        row = get_or_create_settings(db)
        db.commit()

        fake_client = AsyncMock()
        fake_client.search_assets = AsyncMock(return_value=_make_fake_page([_make_fake_asset()]))
        fake_client.get_asset_data = AsyncMock(return_value=_fake_image_bytes())
        fake_client.get_asset_exif = AsyncMock(return_value={"iso": 200})

        effects_config = {"ai_fantasy_hero": {"enabled": True, "weight": 1, "config": {}}}

        with (
            patch("app.services.generation.engine.build_immich_client", return_value=fake_client),
            patch("app.services.generation.engine.get_settings") as mock_cfg,
            patch("app.services.generation.engine._send_gen_notification", new=AsyncMock()),
            patch(
                "app.services.generation.engine.random.choices",
                return_value=[("ai_fantasy_hero", {"enabled": True, "weight": 1, "config": {}})],
            ),
            # Mock module class
            patch(
                "app.services.generation.engine.MODULES",
                {
                    "ai_fantasy_hero": MagicMock(
                        label="AI Fantasy Hero",
                        run=AsyncMock(
                            return_value=MagicMock(
                                image_bytes=_fake_image_bytes(),
                                generation_type="ai_fantasy_hero",
                                provider="openai",
                                model="gpt-image-1",
                                config={
                                    "prompt_enrichment_context": {
                                        "album_name": "Vacation Album",
                                        "people_names": ["Alice"],
                                        "people_prompt_hint": "Immich identified these people in the source photo: Alice. Face positions: Alice is in the upper left.",
                                        "exif_summary": "Camera: Sony A7; Exposure: ISO 400",
                                        "context_hint": "Album: Vacation Album\nDetected people: Alice\nImmich identified these people in the source photo: Alice. Face positions: Alice is in the upper left.\nEXIF: Camera: Sony A7; Exposure: ISO 400",
                                    }
                                },
                                source_asset_ids=["asset-1"],
                                title="Hero Title",
                                summary="Hero Summary",
                            )
                        ),
                    )
                },
            ),
        ):
            mock_cfg.return_value.data_dir = tmp_path
            row.default_ai_provider = "none"
            result = asyncio.run(
                run_generation_cycle(
                    db, row, "task-tags", force=True, effects_config=effects_config, filters=_get_test_filters()
                )
            )

        assert result is not None
        entry = db.query(GenerationHistoryModel).filter_by(task_id="task-tags").first()
        assert entry is not None
        assert entry.tags_json is not None
        tags = json.loads(entry.tags_json)
        assert "AI" in tags
        assert "Fantasy Hero" in tags
    finally:
        db.close()


def test_run_generation_cycle_ai_module_uses_final_vision_image(tmp_path):
    db = _setup_db()
    try:
        row = get_or_create_settings(db)
        db.commit()

        _create_ai_vision_schedule(
            db,
            suffix="",
            groups_json=json.dumps({"ai_anime": {"enabled": True, "weight": 1, "config": {}}}),
        )

        source_bytes = _fake_image_bytes_color((11, 22, 33))
        final_bytes = _fake_image_bytes_color((44, 55, 66))

        fake_client = AsyncMock()
        fake_client.search_assets = AsyncMock(return_value=_make_fake_page([_make_fake_asset()]))
        fake_client.get_asset_data = AsyncMock(return_value=source_bytes)
        fake_client.get_asset_exif = AsyncMock(return_value={})

        module_run = AsyncMock(
            return_value=MagicMock(
                image_bytes=final_bytes,
                generation_type="ai_anime",
                provider="openai",
                model="gpt-image-1",
                config={
                    "prompt_enrichment_context": {
                        "album_name": "Vacation Album",
                        "people_names": ["Alice"],
                        "people_prompt_hint": "Immich identified these people in the source photo: Alice. Face positions: Alice is in the upper left.",
                        "exif_summary": "Camera: Sony A7; Exposure: ISO 400",
                        "context_hint": "Album: Vacation Album\nDetected people: Alice\nImmich identified these people in the source photo: Alice. Face positions: Alice is in the upper left.\nEXIF: Camera: Sony A7; Exposure: ISO 400",
                    }
                },
                source_asset_ids=["asset-1"],
                title="Module Title",
                summary="Module Summary",
            )
        )

        ai_calls: list[bytes] = []

        async def fake_analyze(settings, image_bytes, provider=None, model=None, prompt=None, context_hint=None):
            ai_calls.append(image_bytes)
            if image_bytes == source_bytes:
                return AIVisionResult(
                    title="Source Title",
                    summary="Source Summary",
                    tags=["source"],
                    token_count=11,
                    provider="openai",
                    model="gpt-4o-mini",
                )
            if image_bytes == final_bytes:
                return AIVisionResult(
                    title="Final Title",
                    summary="Final Summary",
                    tags=["final"],
                    token_count=22,
                    provider="openai",
                    model="gpt-4o-mini",
                )
            raise AssertionError("Unexpected image bytes passed to AI Vision")

        effects_config = {"ai_anime": {"enabled": True, "weight": 1, "config": {}}}

        with (
            patch("app.services.generation.engine.build_immich_client", return_value=fake_client),
            patch("app.services.generation.engine.get_settings") as mock_cfg,
            patch("app.services.generation.engine._send_gen_notification", new=AsyncMock()),
            patch(
                "app.services.generation.engine.random.choices",
                return_value=[("ai_anime", {"enabled": True, "weight": 1, "config": {}})],
            ),
            patch(
                "app.services.generation.engine.MODULES",
                {"ai_anime": MagicMock(label="AI Anime", run=module_run)},
            ),
            patch("app.services.generation.engine.analyze_image", side_effect=fake_analyze),
        ):
            mock_cfg.return_value.data_dir = tmp_path
            result = asyncio.run(
                run_generation_cycle(
                    db,
                    row,
                    "task-final-vision",
                    force=True,
                    effects_config=effects_config,
                    filters=_get_test_filters(),
                )
            )

        assert result is not None
        assert len(ai_calls) == 2
        assert {ai_calls[0], ai_calls[1]} == {source_bytes, final_bytes}

        entry = db.query(GenerationHistoryModel).filter_by(task_id="task-final-vision").first()
        assert entry is not None
        assert entry.title == "Final Title"
        assert entry.summary == "Final Summary"
        tags = json.loads(entry.tags_json)
        assert tags == ["final", "AI", "Anime"]
        config = json.loads(entry.config_json)
        provenance = config["metadata_provenance"]
        assert provenance["title_source"] == "final_vision"
        assert provenance["summary_source"] == "final_vision"
        assert provenance["tags_source"] == "final_vision"
        assert provenance["final_vision"]["succeeded"] is True
        assert provenance["source_vision"]["succeeded"] is True
        assert provenance["tag_injections"] == ["AI", "Anime"]
        assert provenance["prompt_enrichment_context"]["album_name"] == "Vacation Album"
        assert any(item.get("stage") == "prompt_enrichment_context" for item in config["task_trace"])
        assert entry.provider == "openai"
        assert entry.model == "gpt-image-1"
    finally:
        db.close()


def test_run_generation_cycle_uses_people_context_for_source_vision(tmp_path):
    db = _setup_db()
    try:
        row = get_or_create_settings(db)
        db.commit()

        _create_ai_vision_schedule(
            db,
            suffix="people",
            groups_json=json.dumps({"instafilter": {"enabled": True, "weight": 1, "config": {"styles": ["aden"]}}}),
        )

        source_bytes = _fake_image_bytes_color((11, 22, 33))
        fake_asset = SimpleNamespace(
            id="asset-1",
            original_file_name="photo.jpg",
            created_at="2024-06-15T10:30:00.000Z",
            people=[SimpleNamespace(id="person-1", name="Alice")],
        )
        fake_client = AsyncMock()
        fake_client.search_assets = AsyncMock(return_value=_make_fake_page([fake_asset]))
        fake_client.get_asset_data = AsyncMock(return_value=source_bytes)
        fake_client.get_asset_exif = AsyncMock(return_value={})
        fake_client.get_asset_info = AsyncMock(
            return_value={
                "people": [
                    {
                        "id": "person-1",
                        "name": "Alice",
                        "faces": [
                            {
                                "id": "face-1",
                                "imageWidth": 400,
                                "imageHeight": 300,
                                "boundingBoxX1": 0,
                                "boundingBoxY1": 0,
                                "boundingBoxX2": 100,
                                "boundingBoxY2": 120,
                            }
                        ],
                    }
                ]
            }
        )

        module_run = AsyncMock(
            return_value=MagicMock(
                image_bytes=_fake_image_bytes_color((44, 55, 66)),
                generation_type="instafilter",
                provider="local",
                model="pil",
                config={},
                source_asset_ids=["asset-1"],
                title="Module Title",
                summary="Module Summary",
            )
        )

        ai_calls: list[dict[str, object]] = []

        async def fake_analyze(settings, image_bytes, provider=None, model=None, prompt=None, context_hint=None):
            ai_calls.append(
                {
                    "bytes": image_bytes,
                    "prompt": prompt,
                    "context_hint": context_hint,
                }
            )
            return AIVisionResult(
                title="Source Title",
                summary="Source Summary",
                tags=["source"],
                token_count=11,
                provider="openai",
                model="gpt-4o-mini",
            )

        effects_config = {"instafilter": {"enabled": True, "weight": 1, "config": {"styles": ["aden"]}}}

        with (
            patch("app.services.generation.engine.build_immich_client", return_value=fake_client),
            patch("app.services.generation.engine.get_settings") as mock_cfg,
            patch("app.services.generation.engine._send_gen_notification", new=AsyncMock()),
            patch(
                "app.services.generation.engine.random.choices",
                return_value=[("instafilter", {"enabled": True, "weight": 1, "config": {"styles": ["aden"]}})],
            ),
            patch(
                "app.services.generation.engine.MODULES",
                {"instafilter": MagicMock(label="Instafilter", run=module_run)},
            ),
            patch("app.services.generation.engine.analyze_image", side_effect=fake_analyze),
        ):
            mock_cfg.return_value.data_dir = tmp_path
            result = asyncio.run(
                run_generation_cycle(
                    db,
                    row,
                    "task-people-context",
                    force=True,
                    effects_config=effects_config,
                    filters=_get_test_filters(),
                )
            )

        assert result is not None
        assert (
            ai_calls[0]["context_hint"]
            == "Immich identified these people in the source photo: Alice. Face positions: Alice is in the upper left."
        )
        entry = db.query(GenerationHistoryModel).filter_by(task_id="task-people-context").first()
        assert entry is not None
        config = json.loads(entry.config_json)
        provenance = config["metadata_provenance"]
        assert provenance["people_context"]["used"] is True
        assert provenance["people_context"]["names"] == ["Alice"]
        assert provenance["source_vision"]["people_context_used"] is True
    finally:
        db.close()
