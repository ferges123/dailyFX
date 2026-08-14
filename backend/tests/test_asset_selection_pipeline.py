import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _contract_helpers import configure_contract_test_db

from app.database import SessionLocal
from app.database import init_db as _init_db
from app.immich.models import ImmichSearchFilters
from app.models.asset_usage import AssetUsageModel
from app.services.generation.pipeline.assets import _pipeline_retrieve_and_select_assets, rank_source_assets_for_effect
from app.services.generation.pipeline.shared import GenerationModuleSelection, GenerationPipelineContext
from app.services.immich import get_or_create_settings

test_db = configure_contract_test_db("asset_selection_pipeline")


def init_db():
    _init_db()


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    db = SessionLocal()
    try:
        db.query(AssetUsageModel).delete()
        db.commit()
        yield db
    finally:
        db.close()


def _make_mock_asset(asset_id, filename="photo.jpg"):
    asset = MagicMock()
    asset.id = asset_id
    asset.original_file_name = filename
    asset.created_at = "2026-05-12T10:00:00Z"
    return asset


def _make_mock_page(items):
    page = MagicMock()
    page.items = items
    page.next_page = None
    return page


@patch("app.services.generation.pipeline.assets._search_assets_for_generation")
def test_select_prefers_never_used(mock_search, setup_db):
    db = setup_db
    settings = get_or_create_settings(db)
    settings.ai_photo_selection_enabled = False
    db.commit()

    # Setup database registry state: asset-1 is accepted, asset-2 is released, asset-3 is never used
    u1 = AssetUsageModel(
        asset_id="asset-1",
        task_id="task-old-1",
        generation_type="duotone",
        usage_source="automatic",
        status="accepted",
        accepted_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
    )
    u2 = AssetUsageModel(
        asset_id="asset-2",
        task_id="task-old-2",
        generation_type="collage",
        usage_source="automatic",
        status="released",
        release_reason="rejected",
        released_at=datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc),
    )
    db.add_all([u1, u2])
    db.commit()

    # Mock search response containing all 3 assets
    assets = [
        _make_mock_asset("asset-1"),
        _make_mock_asset("asset-2"),
        _make_mock_asset("asset-3"),
    ]
    mock_search.return_value = (MagicMock(), _make_mock_page(assets))

    # Setup context and module selection
    ctx = GenerationPipelineContext(
        db=db, settings=settings, task_id="auto-task-1", filters=ImmichSearchFilters(album_ids=None, person_filters=[])
    )
    module = MagicMock()
    module.source_asset_count = 1
    module_selection = GenerationModuleSelection(name="duotone", module=module, config={})

    # Execute
    res = asyncio.run(_pipeline_retrieve_and_select_assets(ctx, module_selection))
    assert res is not None
    client, page, page_items, trace = res

    # Verify that asset-3 (never used) was selected
    assert len(page_items) == 1
    assert page_items[0].id == "asset-3"
    assert ctx.asset_selection["selection_reason_code"] == "never_used"


@patch("app.services.generation.pipeline.assets._search_assets_for_generation")
def test_select_prefers_released_over_accepted(mock_search, setup_db):
    db = setup_db
    settings = get_or_create_settings(db)
    settings.ai_photo_selection_enabled = False
    db.commit()

    # asset-1 is accepted, asset-2 is released (no never-used asset exists in search results)
    u1 = AssetUsageModel(
        asset_id="asset-1",
        task_id="task-old-1",
        generation_type="duotone",
        usage_source="automatic",
        status="accepted",
        accepted_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
    )
    u2 = AssetUsageModel(
        asset_id="asset-2",
        task_id="task-old-2",
        generation_type="collage",
        usage_source="automatic",
        status="released",
        release_reason="rejected",
        released_at=datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc),
    )
    db.add_all([u1, u2])
    db.commit()

    assets = [
        _make_mock_asset("asset-1"),
        _make_mock_asset("asset-2"),
    ]
    mock_search.return_value = (MagicMock(), _make_mock_page(assets))

    ctx = GenerationPipelineContext(
        db=db, settings=settings, task_id="auto-task-2", filters=ImmichSearchFilters(album_ids=None, person_filters=[])
    )
    module = MagicMock()
    module.source_asset_count = 1
    module_selection = GenerationModuleSelection(name="duotone", module=module, config={})

    res = asyncio.run(_pipeline_retrieve_and_select_assets(ctx, module_selection))
    assert res is not None
    client, page, page_items, trace = res

    # Verify that asset-2 (released) was selected
    assert len(page_items) == 1
    assert page_items[0].id == "asset-2"
    assert ctx.asset_selection["selection_reason_code"] == "returned_after_rejection"


@patch("app.services.generation.pipeline.assets._search_assets_for_generation")
def test_select_excludes_pending_completely(mock_search, setup_db):
    db = setup_db
    settings = get_or_create_settings(db)
    settings.ai_photo_selection_enabled = False
    db.commit()

    # asset-1 is pending, asset-2 is accepted
    u1 = AssetUsageModel(
        asset_id="asset-1", task_id="task-old-1", generation_type="duotone", usage_source="automatic", status="pending"
    )
    u2 = AssetUsageModel(
        asset_id="asset-2",
        task_id="task-old-2",
        generation_type="collage",
        usage_source="automatic",
        status="accepted",
        accepted_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
    )
    db.add_all([u1, u2])
    db.commit()

    assets = [
        _make_mock_asset("asset-1"),
        _make_mock_asset("asset-2"),
    ]
    mock_search.return_value = (MagicMock(), _make_mock_page(assets))

    ctx = GenerationPipelineContext(
        db=db, settings=settings, task_id="auto-task-3", filters=ImmichSearchFilters(album_ids=None, person_filters=[])
    )
    module = MagicMock()
    module.source_asset_count = 1
    module_selection = GenerationModuleSelection(name="duotone", module=module, config={})

    res = asyncio.run(_pipeline_retrieve_and_select_assets(ctx, module_selection))
    assert res is not None
    client, page, page_items, trace = res

    # Verify that asset-2 is selected because asset-1 is pending (excluded)
    assert len(page_items) == 1
    assert page_items[0].id == "asset-2"
    assert ctx.asset_selection["selection_reason_code"] == "least_recently_accepted"


@patch("app.services.generation.pipeline.assets._search_assets_for_generation")
def test_select_oldest_accepted_when_all_accepted(mock_search, setup_db):
    db = setup_db
    settings = get_or_create_settings(db)
    settings.ai_photo_selection_enabled = False
    db.commit()

    # asset-1 accepted on July 5, asset-2 accepted on July 1
    u1 = AssetUsageModel(
        asset_id="asset-1",
        task_id="task-old-1",
        generation_type="duotone",
        usage_source="automatic",
        status="accepted",
        accepted_at=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
    )
    u2 = AssetUsageModel(
        asset_id="asset-2",
        task_id="task-old-2",
        generation_type="collage",
        usage_source="automatic",
        status="accepted",
        accepted_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
    )
    db.add_all([u1, u2])
    db.commit()

    assets = [
        _make_mock_asset("asset-1"),
        _make_mock_asset("asset-2"),
    ]
    mock_search.return_value = (MagicMock(), _make_mock_page(assets))

    ctx = GenerationPipelineContext(
        db=db, settings=settings, task_id="auto-task-4", filters=ImmichSearchFilters(album_ids=None, person_filters=[])
    )
    module = MagicMock()
    module.source_asset_count = 1
    module_selection = GenerationModuleSelection(name="duotone", module=module, config={})

    res = asyncio.run(_pipeline_retrieve_and_select_assets(ctx, module_selection))
    assert res is not None
    client, page, page_items, trace = res

    # Verify that asset-2 (oldest accepted) was selected
    assert len(page_items) == 1
    assert page_items[0].id == "asset-2"


@patch("app.services.generation.pipeline.assets._search_assets_for_generation")
def test_multiple_search_attempts_automatic_runs(mock_search, setup_db):
    db = setup_db
    settings = get_or_create_settings(db)
    settings.ai_photo_selection_enabled = False
    db.commit()

    # Setup database registry state: asset-1 is accepted
    u1 = AssetUsageModel(
        asset_id="asset-1",
        task_id="task-old-1",
        generation_type="duotone",
        usage_source="automatic",
        status="accepted",
        accepted_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
    )
    db.add(u1)
    db.commit()

    # Attempt 1 returns only asset-1 (already accepted)
    # Attempt 2 returns asset-1 and asset-2 (never used)
    call_count = 0

    def mock_search_fn(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            page = _make_mock_page([_make_mock_asset("asset-1")])
            page.next_page = "2"
            return MagicMock(), page
        else:
            return MagicMock(), _make_mock_page([_make_mock_asset("asset-1"), _make_mock_asset("asset-2")])

    mock_search.side_effect = mock_search_fn

    ctx = GenerationPipelineContext(
        db=db, settings=settings, task_id="auto-task-5", filters=ImmichSearchFilters(album_ids=None, person_filters=[])
    )
    module = MagicMock()
    module.source_asset_count = 1
    module_selection = GenerationModuleSelection(name="duotone", module=module, config={})

    res = asyncio.run(_pipeline_retrieve_and_select_assets(ctx, module_selection))
    assert res is not None
    client, page, page_items, trace = res

    # Verify that asset-2 was chosen and it took 2 attempts
    assert len(page_items) == 1
    assert page_items[0].id == "asset-2"
    assert ctx.asset_selection["search_attempts"] == 2
    assert ctx.asset_selection["selection_reason_code"] == "never_used"


@patch("app.services.generation.pipeline.assets._search_assets_for_generation")
def test_automatic_selection_advances_page_after_dailyfx_results(mock_search, setup_db):
    db = setup_db
    settings = get_or_create_settings(db)
    settings.ai_photo_selection_enabled = False
    db.commit()

    first_page = _make_mock_page([_make_mock_asset("asset-dailyfx", "dailyfx-output.png")])
    first_page.next_page = "2"
    second_page = _make_mock_page([_make_mock_asset("asset-usable", "family.jpg")])
    mock_search.side_effect = [(MagicMock(), first_page), (MagicMock(), second_page)]

    ctx = GenerationPipelineContext(
        db=db, settings=settings, task_id="auto-task-pages", filters=ImmichSearchFilters(person_filters=[])
    )
    module = MagicMock()
    module.source_asset_count = 1
    module_selection = GenerationModuleSelection(name="duotone", module=module, config={})

    result = asyncio.run(_pipeline_retrieve_and_select_assets(ctx, module_selection))

    assert result is not None
    assert result[2][0].id == "asset-usable"
    assert [call.kwargs["page"] for call in mock_search.call_args_list] == [1, 2]


@patch("app.services.generation.pipeline.assets._search_assets_for_generation")
@patch("app.services.generation.pipeline.assets.debug_log")
def test_no_candidates_records_dailyfx_exclusion_diagnostics(mock_debug_log, mock_search, setup_db):
    db = setup_db
    settings = get_or_create_settings(db)
    settings.ai_photo_selection_enabled = False
    db.commit()

    page = _make_mock_page(
        [
            _make_mock_asset("asset-dailyfx-1", "dailyfx-one.png"),
            _make_mock_asset("asset-dailyfx-2", "DailyFX-two.png"),
        ]
    )
    mock_search.return_value = (MagicMock(), page)
    ctx = GenerationPipelineContext(
        db=db, settings=settings, task_id="auto-task-empty", filters=ImmichSearchFilters(person_filters=[])
    )
    module = MagicMock()
    module.source_asset_count = 1
    module_selection = GenerationModuleSelection(name="duotone", module=module, config={})

    result = asyncio.run(_pipeline_retrieve_and_select_assets(ctx, module_selection))

    assert result is None
    assert ctx.asset_selection["raw_result_count"] == 2
    assert ctx.asset_selection["dailyfx_generated_count"] == 2
    assert ctx.asset_selection["usable_unique_count"] == 0
    assert ctx.asset_selection["search_attempts"] == 1
    assert ctx.current_step == "failed"
    mock_debug_log.assert_any_call(
        "Skipping: no available candidates found after exclusions",
        task_id="auto-task-empty",
        missing_id_count=0,
        duplicate_count=0,
        dailyfx_generated_count=2,
        pending_excluded_count=0,
    )


@patch("app.services.generation.pipeline.assets._search_assets_for_generation")
def test_manual_selection_override(mock_search, setup_db):
    db = setup_db
    settings = get_or_create_settings(db)
    settings.ai_photo_selection_enabled = False
    db.commit()

    # asset-1 is pending, but manual selection overrides protection and selects it anyway
    u1 = AssetUsageModel(
        asset_id="asset-1", task_id="task-old-1", generation_type="duotone", usage_source="automatic", status="pending"
    )
    db.add(u1)
    db.commit()

    assets = [
        _make_mock_asset("asset-1"),
        _make_mock_asset("asset-2"),
    ]
    mock_search.return_value = (MagicMock(), _make_mock_page(assets))

    ctx = GenerationPipelineContext(
        db=db,
        settings=settings,
        task_id="manual-task-1",
        filters=ImmichSearchFilters(album_ids=None, person_filters=[]),
        selected_asset_ids=["asset-1"],
    )
    module = MagicMock()
    module.source_asset_count = 1
    module_selection = GenerationModuleSelection(name="duotone", module=module, config={})

    res = asyncio.run(_pipeline_retrieve_and_select_assets(ctx, module_selection))
    assert res is not None
    client, page, page_items, trace = res

    # Verify that asset-1 (manually specified) was selected despite pending status
    assert len(page_items) == 1
    assert page_items[0].id == "asset-1"
    assert ctx.asset_selection["selection_reason_code"] == "manual_override"


@patch("app.services.generation.pipeline.assets.analyze_images")
def test_rank_source_assets_initial_success(mock_analyze):
    assets = [_make_mock_asset(f"asset-{i}") for i in range(1, 5)]
    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=b"img")
    settings = MagicMock(default_ai_provider="xiaomi")
    module = MagicMock()

    mock_result = MagicMock()
    mock_result.summary = json.dumps({"selected_index": 2, "selection_reason": "Good"})
    mock_result.title = "Ranking"
    mock_analyze.return_value = mock_result

    trace = {}
    selected = asyncio.run(
        rank_source_assets_for_effect(
            client=client, settings=settings, candidates=assets, module=module, task_id="test", trace=trace
        )
    )

    assert selected.id == "asset-2"
    assert trace["succeeded"] is True
    assert trace["retry_count"] == 0
    assert mock_analyze.call_count == 1


@patch("app.services.generation.pipeline.assets.analyze_images")
def test_rank_source_assets_malformed_then_retry_success(mock_analyze):
    assets = [_make_mock_asset(f"asset-{i}") for i in range(1, 5)]
    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=b"img")
    settings = MagicMock(default_ai_provider="xiaomi")
    module = MagicMock()

    fail_result = MagicMock()
    fail_result.summary = "Just some prose, no JSON."
    fail_result.title = "Title"

    success_result = MagicMock()
    success_result.summary = "```json\n" + json.dumps({"selected_index": 3, "selection_reason": "Better"}) + "\n```"
    success_result.title = "Title"

    mock_analyze.side_effect = [fail_result, success_result]

    trace = {}
    selected = asyncio.run(
        rank_source_assets_for_effect(
            client=client, settings=settings, candidates=assets, module=module, task_id="test", trace=trace
        )
    )

    assert selected.id == "asset-3"
    assert trace["succeeded"] is True
    assert trace["retry_count"] == 1
    assert mock_analyze.call_count == 2
    assert "ONLY raw JSON" in mock_analyze.call_args_list[1][1]["prompt"]


@patch("app.services.generation.pipeline.assets.analyze_images")
def test_rank_source_assets_double_failure_local_fallback(mock_analyze):
    assets = [
        _make_mock_asset("asset-1"),
        _make_mock_asset("asset-2"),
    ]
    # Make asset-2 more recent
    assets[0].created_at = "2026-05-12T10:00:00Z"
    assets[1].created_at = "2026-05-13T10:00:00Z"

    client = AsyncMock()
    client.get_asset_data = AsyncMock(return_value=b"img")
    settings = MagicMock(default_ai_provider="xiaomi")
    module = MagicMock()

    mock_analyze.side_effect = Exception("Vision API failed")

    trace = {}
    selected = asyncio.run(
        rank_source_assets_for_effect(
            client=client, settings=settings, candidates=assets, module=module, task_id="test", trace=trace
        )
    )

    # asset-2 should be selected because it's newer (deterministic fallback)
    assert selected.id == "asset-2"
    assert trace["succeeded"] is False
    assert trace["retry_count"] == 1
    assert "Vision API failed" in trace["failure_causes"][0]
    assert trace["fallback_strategy"] is not None
