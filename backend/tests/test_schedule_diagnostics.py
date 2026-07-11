import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _contract_helpers import configure_contract_test_db

from app.api.routes_schedules import get_schedule_diagnostics
from app.database import SessionLocal
from app.database import init_db as _init_db
from app.models.asset_usage import AssetUsageModel
from app.models.effect_preset import EffectPresetModel
from app.models.filter_preset import FilterPresetModel
from app.models.schedule import ScheduleModel
from app.services.immich import get_or_create_settings

test_db = configure_contract_test_db("schedule_diagnostics")


def init_db():
    _init_db()


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    db = SessionLocal()
    try:
        db.query(AssetUsageModel).delete()
        db.query(ScheduleModel).delete()
        db.query(FilterPresetModel).delete()
        db.query(EffectPresetModel).delete()
        db.commit()
        yield db
    finally:
        db.close()


def _make_mock_asset(asset_id, filename="photo.jpg", created_at="2026-05-12T10:00:00Z"):
    asset = MagicMock()
    asset.id = asset_id
    asset.original_file_name = filename
    asset.created_at = created_at
    return asset


def _make_mock_page(items, total=None):
    page = MagicMock()
    page.items = items
    page.total = total if total is not None else len(items)
    return page


@patch("app.services.immich.build_immich_client")
def test_schedule_diagnostics(mock_build_client, setup_db):
    db = setup_db
    _ = get_or_create_settings(db)
    db.commit()

    # Create filter preset
    fp = FilterPresetModel(
        name="test-filters",
        album_ids_json="[]",
        person_filters_json="[]",
        media_type="photo",
    )
    # Create effect preset
    ep = EffectPresetModel(
        name="test-effects",
        groups_json="{}",
    )
    db.add_all([fp, ep])
    db.commit()

    # Create schedule
    schedule = ScheduleModel(
        name="test-schedule",
        enabled=True,
        schedule_expr="weekly",
        filter_preset_id=fp.id,
        effect_preset_id=ep.id,
        album_name="Test Album",
        ai_vision_provider="none",
        ai_vision_model="gpt-4o-mini",
        ai_image_provider="none",
        ai_image_model="gpt-image-1",
        ai_prompt_enrichment=False,
    )
    db.add(schedule)
    db.commit()

    # Setup database registry state:
    # asset-1 is accepted, asset-2 is released, asset-3 is pending, asset-4 is never used
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
    u3 = AssetUsageModel(
        asset_id="asset-3", task_id="task-old-3", generation_type="duotone", usage_source="automatic", status="pending"
    )
    db.add_all([u1, u2, u3])
    db.commit()

    # Mock Immich get_assets return
    assets = [
        _make_mock_asset("asset-1", created_at="2026-05-12T10:00:00Z"),
        _make_mock_asset("asset-2", created_at="2026-05-13T10:00:00Z"),
        _make_mock_asset("asset-3", created_at="2026-05-14T10:00:00Z"),
        _make_mock_asset("asset-4", created_at="2026-05-15T10:00:00Z"),
    ]
    mock_client = AsyncMock()
    mock_client.get_assets.return_value = _make_mock_page(assets, total=10)
    mock_build_client.return_value = mock_client

    # Call diagnostics route
    res = asyncio.run(get_schedule_diagnostics(schedule_id=schedule.id, db=db))

    assert res.total_candidates == 10
    assert res.never_used_count == 1
    assert res.released_count == 1
    assert res.accepted_count == 1
    assert res.pending_count == 1

    # Selection order:
    # 1. never_used (asset-4)
    # 2. released (asset-2)
    # 3. accepted (asset-1)
    # asset-3 is pending, so it is excluded from selection order!
    assert len(res.selection_order) == 3
    assert res.selection_order[0].id == "asset-4"
    assert res.selection_order[0].status == "never_used"
    assert res.selection_order[1].id == "asset-2"
    assert res.selection_order[1].status == "released"
    assert res.selection_order[2].id == "asset-1"
    assert res.selection_order[2].status == "accepted"
