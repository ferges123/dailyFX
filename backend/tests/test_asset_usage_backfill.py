import json
import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from _contract_helpers import configure_contract_test_db, make_generation_history_row

from app.database import SessionLocal
from app.database import init_db as _init_db
from app.models.asset_usage import AssetUsageModel
from app.models.generation_history import GenerationHistoryModel
from app.services.generation.asset_usage import backfill_asset_usage

test_db = configure_contract_test_db("asset_usage_backfill")


def init_db():
    _init_db()


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    db = SessionLocal()
    try:
        # Clean up database tables for fresh test run
        db.query(AssetUsageModel).delete()
        db.query(GenerationHistoryModel).delete()
        db.commit()
        yield db
    finally:
        db.close()


def test_asset_usage_model_creation(setup_db):
    db = setup_db
    usage = AssetUsageModel(
        asset_id="asset-123",
        task_id="task-456",
        schedule_id=1,
        generation_type="collage",
        usage_source="automatic",
        status="pending",
        selected_at=datetime.now(timezone.utc),
    )
    db.add(usage)
    db.commit()

    retrieved = db.query(AssetUsageModel).filter_by(task_id="task-456").first()
    assert retrieved is not None
    assert retrieved.asset_id == "asset-123"
    assert retrieved.usage_source == "automatic"
    assert retrieved.status == "pending"


def test_asset_usage_uniqueness_constraint(setup_db):
    db = setup_db
    usage1 = AssetUsageModel(
        asset_id="asset-1",
        task_id="task-1",
        schedule_id=1,
        generation_type="duotone",
        usage_source="automatic",
        status="pending",
        selected_at=datetime.now(timezone.utc),
    )
    usage2 = AssetUsageModel(
        asset_id="asset-1",
        task_id="task-1",
        schedule_id=2,
        generation_type="polaroid",
        usage_source="manual",
        status="accepted",
        selected_at=datetime.now(timezone.utc),
    )
    db.add(usage1)
    db.commit()

    db.add(usage2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_backfill_mapping_and_idempotency(setup_db):
    db = setup_db

    # Create fake history records
    hist1 = make_generation_history_row(
        task_id="auto-task-pending",
        status="PENDING_REVIEW",
        source_asset_ids=json.dumps(["asset-pending-1", "asset-pending-2"]),
        created_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
    )
    hist2 = make_generation_history_row(
        task_id="auto-task-accepted",
        status="UPLOADED",
        source_asset_ids=json.dumps(["asset-accepted-1"]),
        accepted_at=datetime(2026, 7, 2, 11, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc),
    )
    hist3 = make_generation_history_row(
        task_id="manual-task-rejected",
        status="REJECTED",
        source_asset_ids=json.dumps(["asset-rejected-1"]),
        created_at=datetime(2026, 7, 3, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 3, 10, 5, tzinfo=timezone.utc),
    )
    hist4 = make_generation_history_row(
        task_id="manual-task-failed",
        status="FAILED",
        source_asset_ids=json.dumps(["asset-failed-1"]),
        created_at=datetime(2026, 7, 4, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 4, 10, 10, tzinfo=timezone.utc),
    )

    db.add_all([hist1, hist2, hist3, hist4])
    db.commit()

    # Run backfill
    backfill_asset_usage(db)

    # Assert correct counts and mapping
    usages = db.query(AssetUsageModel).order_by(AssetUsageModel.task_id).all()
    assert len(usages) == 5  # 2 + 1 + 1 + 1

    # auto-task-pending assets
    pending_usages = db.query(AssetUsageModel).filter(AssetUsageModel.task_id == "auto-task-pending").all()
    assert len(pending_usages) == 2
    assert {u.asset_id for u in pending_usages} == {"asset-pending-1", "asset-pending-2"}
    for u in pending_usages:
        assert u.status == "pending"
        assert u.usage_source == "automatic"

    # auto-task-accepted assets
    accepted_usage = db.query(AssetUsageModel).filter(AssetUsageModel.task_id == "auto-task-accepted").first()
    assert accepted_usage is not None
    assert accepted_usage.asset_id == "asset-accepted-1"
    assert accepted_usage.status == "accepted"
    assert accepted_usage.accepted_at == datetime(2026, 7, 2, 11, 0, tzinfo=timezone.utc)

    # manual-task-rejected assets
    rejected_usage = db.query(AssetUsageModel).filter(AssetUsageModel.task_id == "manual-task-rejected").first()
    assert rejected_usage is not None
    assert rejected_usage.status == "released"
    assert rejected_usage.release_reason == "rejected"
    assert rejected_usage.released_at == datetime(2026, 7, 3, 10, 5, tzinfo=timezone.utc)
    assert rejected_usage.usage_source == "manual"

    # manual-task-failed assets
    failed_usage = db.query(AssetUsageModel).filter(AssetUsageModel.task_id == "manual-task-failed").first()
    assert failed_usage is not None
    assert failed_usage.status == "released"
    assert failed_usage.release_reason == "failed"
    assert failed_usage.released_at == datetime(2026, 7, 4, 10, 10, tzinfo=timezone.utc)

    # Test idempotency (run backfill again, nothing should change)
    backfill_asset_usage(db)
    assert db.query(AssetUsageModel).count() == 5


def test_backfill_handles_invalid_or_duplicate_json(setup_db):
    db = setup_db

    # Invalid JSON
    hist1 = make_generation_history_row(
        task_id="task-invalid-json",
        status="PENDING_REVIEW",
        source_asset_ids="invalid-json{",
    )
    # Duplicate asset IDs inside the same task
    hist2 = make_generation_history_row(
        task_id="task-duplicates",
        status="PENDING_REVIEW",
        source_asset_ids=json.dumps(["dup-1", "dup-1", "dup-2", ""]),
    )

    db.add_all([hist1, hist2])
    db.commit()

    backfill_asset_usage(db)

    # Invalid JSON should be skipped, duplicates should be deduped
    assert db.query(AssetUsageModel).filter_by(task_id="task-invalid-json").count() == 0

    duplicate_usages = db.query(AssetUsageModel).filter_by(task_id="task-duplicates").all()
    assert len(duplicate_usages) == 2
    assert {u.asset_id for u in duplicate_usages} == {"dup-1", "dup-2"}


def test_registry_service_status_and_actions(setup_db):
    db = setup_db

    from app.services.generation.asset_usage import (
        get_assets_usage_status,
        record_assets_usage_pending,
        accept_task_assets,
        release_task_assets,
    )

    # 1. Record pending for Task 1
    record_assets_usage_pending(
        db,
        task_id="task-1",
        asset_ids=["asset-a", "asset-b"],
        generation_type="collage",
        usage_source="automatic",
        schedule_id=5,
    )

    # Check status (pending)
    status = get_assets_usage_status(db, ["asset-a", "asset-b", "asset-c"])
    assert status["asset-a"]["is_unavailable"] is True
    assert status["asset-a"]["ever_accepted"] is False
    assert status["asset-b"]["is_unavailable"] is True
    assert status["asset-c"]["is_unavailable"] is False

    # Accept Task 1
    accept_task_assets(db, "task-1", accepted_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc))

    # Check status (accepted)
    status = get_assets_usage_status(db, ["asset-a", "asset-b"])
    assert status["asset-a"]["is_unavailable"] is True
    assert status["asset-a"]["ever_accepted"] is True
    assert status["asset-a"]["last_accepted_at"] == datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)

    # 2. Record pending for Task 2 (using asset-a again, representing a retry or another usage)
    record_assets_usage_pending(
        db,
        task_id="task-2",
        asset_ids=["asset-a"],
        generation_type="collage",
        usage_source="automatic",
        schedule_id=5,
    )

    # Release Task 2 with failed reason
    release_task_assets(db, "task-2", reason="failed")

    # Check status after release of Task 2
    status = get_assets_usage_status(db, ["asset-a", "asset-b"])
    assert status["asset-a"]["is_unavailable"] is True  # still True because of Task 1 (accepted)
    assert status["asset-a"]["ever_accepted"] is True  # still True because of Task 1
    assert status["asset-a"]["returned_to_pool"] is True  # True because of Task 2 (released)


