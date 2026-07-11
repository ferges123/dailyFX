import json
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.generation_history import GenerationHistoryModel
from app.models.asset_usage import AssetUsageModel

logger = logging.getLogger(__name__)


def backfill_asset_usage(db: Session) -> None:
    """Idempotently backfills the asset_usage registry from existing generation_history records."""
    try:
        # Load all history records chronologically
        history_records = db.query(GenerationHistoryModel).order_by(GenerationHistoryModel.created_at.asc()).all()
        if not history_records:
            return

        logger.info("Starting asset usage registry backfill from %d history records", len(history_records))
        added_count = 0

        # Get existing unique (task_id, asset_id) pairs to ensure idempotency
        existing_pairs = set(
            db.query(AssetUsageModel.task_id, AssetUsageModel.asset_id).all()
        )

        for record in history_records:
            if not record.source_asset_ids:
                continue

            try:
                asset_ids = json.loads(record.source_asset_ids)
            except Exception:
                continue

            if not isinstance(asset_ids, list):
                continue

            # Deduplicate asset IDs within the same task/generation
            unique_asset_ids = []
            for asset_id in asset_ids:
                if isinstance(asset_id, str) and asset_id.strip() and asset_id not in unique_asset_ids:
                    unique_asset_ids.append(asset_id)

            for asset_id in unique_asset_ids:
                pair = (record.task_id, asset_id)
                if pair in existing_pairs:
                    continue

                # Map history status to asset usage status
                hist_status = (record.status or "").upper()
                if hist_status == "PENDING_REVIEW":
                    mapped_status = "pending"
                    release_reason = None
                    released_at = None
                elif hist_status == "UPLOADED":
                    mapped_status = "accepted"
                    release_reason = None
                    released_at = None
                elif hist_status == "REJECTED":
                    mapped_status = "released"
                    release_reason = "rejected"
                    released_at = record.updated_at
                elif hist_status == "FAILED":
                    mapped_status = "released"
                    release_reason = "failed"
                    released_at = record.updated_at
                else:
                    # Default fallback
                    mapped_status = "released"
                    release_reason = "failed"
                    released_at = record.updated_at

                usage = AssetUsageModel(
                    asset_id=asset_id,
                    task_id=record.task_id,
                    schedule_id=record.schedule_id,
                    generation_type=record.generation_type,
                    usage_source="automatic" if record.task_id.startswith("auto-") else "manual",
                    status=mapped_status,
                    selected_at=record.created_at or datetime.now(timezone.utc),
                    accepted_at=record.accepted_at,
                    released_at=released_at,
                    release_reason=release_reason,
                    created_at=record.created_at or datetime.now(timezone.utc),
                    updated_at=record.updated_at or datetime.now(timezone.utc),
                )
                db.add(usage)
                existing_pairs.add(pair)
                added_count += 1

        if added_count > 0:
            db.commit()
            logger.info("Successfully backfilled %d asset usage records", added_count)
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to run asset usage backfill: %s", exc)


def get_assets_usage_status(db: Session, asset_ids: list[str]) -> dict[str, dict]:
    """
    Returns usage information for a list of asset IDs.
    Returns a dict mapping asset_id to a dict containing:
      - is_unavailable: bool (has status pending or accepted)
      - has_pending: bool (has status pending)
      - ever_accepted: bool (has status accepted)
      - last_accepted_at: datetime | None (max accepted_at for accepted status)
      - returned_to_pool: bool (has status released)
      - last_release_reason: str | None (the last release_reason for released status)
    """
    results = {}
    for aid in asset_ids:
        results[aid] = {
            "is_unavailable": False,
            "has_pending": False,
            "ever_accepted": False,
            "last_accepted_at": None,
            "returned_to_pool": False,
            "last_release_reason": None,
        }

    if not asset_ids:
        return results

    # Query all matching usage records
    usages = db.query(AssetUsageModel).filter(AssetUsageModel.asset_id.in_(asset_ids)).all()

    for usage in usages:
        aid = usage.asset_id
        if aid not in results:
            continue

        if usage.status in ("pending", "accepted"):
            results[aid]["is_unavailable"] = True

        if usage.status == "pending":
            results[aid]["has_pending"] = True

        if usage.status == "accepted":
            results[aid]["ever_accepted"] = True
            if usage.accepted_at:
                current_last = results[aid]["last_accepted_at"]
                if current_last is None or usage.accepted_at > current_last:
                    results[aid]["last_accepted_at"] = usage.accepted_at

        if usage.status == "released":
            results[aid]["returned_to_pool"] = True
            results[aid]["last_release_reason"] = usage.release_reason

    return results


def record_assets_usage_pending(
    db: Session,
    *,
    task_id: str,
    asset_ids: list[str],
    generation_type: str,
    usage_source: str,
    schedule_id: int | None = None,
) -> None:
    """
    Records a pending usage entry for each unique asset in asset_ids under task_id.
    This operation is idempotent.
    """
    if not asset_ids:
        return

    # Deduplicate asset IDs
    unique_asset_ids = []
    for aid in asset_ids:
        if isinstance(aid, str) and aid.strip() and aid not in unique_asset_ids:
            unique_asset_ids.append(aid)

    # Check for existing entries for this task_id to ensure idempotency
    existing_asset_ids = {
        row[0]
        for row in db.query(AssetUsageModel.asset_id)
        .filter(AssetUsageModel.task_id == task_id)
        .all()
    }

    now = datetime.now(timezone.utc)
    added = False
    for asset_id in unique_asset_ids:
        if asset_id in existing_asset_ids:
            continue

        usage = AssetUsageModel(
            asset_id=asset_id,
            task_id=task_id,
            schedule_id=schedule_id,
            generation_type=generation_type,
            usage_source=usage_source,
            status="pending",
            selected_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(usage)
        added = True

    if added:
        db.commit()
        logger.info("Recorded %d asset(s) as pending for task_id=%s", len(unique_asset_ids), task_id)


def accept_task_assets(db: Session, task_id: str, accepted_at: datetime | None = None) -> None:
    """
    Transitions pending asset usage entries for task_id to accepted.
    This operation is idempotent.
    """
    usages = db.query(AssetUsageModel).filter(
        AssetUsageModel.task_id == task_id,
        AssetUsageModel.status == "pending",
    ).all()

    if not usages:
        return

    now = accepted_at or datetime.now(timezone.utc)
    for usage in usages:
        usage.status = "accepted"
        usage.accepted_at = now
        usage.updated_at = now

    db.commit()
    logger.info("Transitioned assets for task_id=%s to accepted", task_id)


def release_task_assets(db: Session, task_id: str, reason: str) -> None:
    """
    Transitions pending (or accepted, if matching reason) asset usage entries for task_id to released.
    This operation is idempotent.
    """
    # Acceptable reasons: "rejected", "failed", "deleted"
    if reason not in ("rejected", "failed", "deleted"):
        raise ValueError(f"Invalid release reason: {reason}")

    usages = db.query(AssetUsageModel).filter(
        AssetUsageModel.task_id == task_id,
    ).all()

    if not usages:
        return

    now = datetime.now(timezone.utc)
    updated = False
    for usage in usages:
        if usage.status != "released":
            usage.status = "released"
            usage.released_at = now
            usage.release_reason = reason
            usage.updated_at = now
            updated = True

    if updated:
        db.commit()
        logger.info("Transitioned assets for task_id=%s to released (reason=%s)", task_id, reason)
