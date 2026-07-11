import json
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from _contract_helpers import configure_contract_test_db

from app.database import SessionLocal
from app.database import init_db as _init_db
from app.models.asset_usage import AssetUsageModel
from app.immich.models import ImmichSearchFilters
from app.services.immich import get_or_create_settings
from app.services.generation.pipeline.shared import GenerationPipelineContext, GenerationModuleSelection
from app.services.generation.pipeline.assets import _pipeline_retrieve_and_select_assets

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
    return page


@patch("app.services.generation.pipeline.assets._search_assets_for_generation")
def test_select_prefers_never_used(mock_search, setup_db):
    db = setup_db
    settings = get_or_create_settings(db)
    settings.ai_photo_selection_enabled = False
    db.commit()

    # Setup database registry state: asset-1 is accepted, asset-2 is released, asset-3 is never used
    u1 = AssetUsageModel(
        asset_id="asset-1", task_id="task-old-1", generation_type="duotone",
        usage_source="automatic", status="accepted", accepted_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    )
    u2 = AssetUsageModel(
        asset_id="asset-2", task_id="task-old-2", generation_type="collage",
        usage_source="automatic", status="released", release_reason="rejected", released_at=datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)
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
        asset_id="asset-1", task_id="task-old-1", generation_type="duotone",
        usage_source="automatic", status="accepted", accepted_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    )
    u2 = AssetUsageModel(
        asset_id="asset-2", task_id="task-old-2", generation_type="collage",
        usage_source="automatic", status="released", release_reason="rejected", released_at=datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)
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
        asset_id="asset-1", task_id="task-old-1", generation_type="duotone",
        usage_source="automatic", status="pending"
    )
    u2 = AssetUsageModel(
        asset_id="asset-2", task_id="task-old-2", generation_type="collage",
        usage_source="automatic", status="accepted", accepted_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
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
        asset_id="asset-1", task_id="task-old-1", generation_type="duotone",
        usage_source="automatic", status="accepted", accepted_at=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
    )
    u2 = AssetUsageModel(
        asset_id="asset-2", task_id="task-old-2", generation_type="collage",
        usage_source="automatic", status="accepted", accepted_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
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
        asset_id="asset-1", task_id="task-old-1", generation_type="duotone",
        usage_source="automatic", status="accepted", accepted_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
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
            return MagicMock(), _make_mock_page([_make_mock_asset("asset-1")])
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
def test_manual_selection_override(mock_search, setup_db):
    db = setup_db
    settings = get_or_create_settings(db)
    settings.ai_photo_selection_enabled = False
    db.commit()

    # asset-1 is pending, but manual selection overrides protection and selects it anyway
    u1 = AssetUsageModel(
        asset_id="asset-1", task_id="task-old-1", generation_type="duotone",
        usage_source="automatic", status="pending"
    )
    db.add(u1)
    db.commit()

    assets = [
        _make_mock_asset("asset-1"),
        _make_mock_asset("asset-2"),
    ]
    mock_search.return_value = (MagicMock(), _make_mock_page(assets))

    ctx = GenerationPipelineContext(
        db=db, settings=settings, task_id="manual-task-1", filters=ImmichSearchFilters(album_ids=None, person_filters=[]),
        selected_asset_ids=["asset-1"]
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
