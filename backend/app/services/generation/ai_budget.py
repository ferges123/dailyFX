from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.ai_usage import AIUsageEventModel

logger = logging.getLogger(__name__)

WINDOW = timedelta(hours=1)
_USAGE_LOCKS: dict[str, Lock] = defaultdict(Lock)


class AIUsageLimitExceededError(RuntimeError):
    pass


def _normalize_usage_type(usage_type: str) -> str:
    value = (usage_type or "").strip().lower()
    if value not in {"vision", "image"}:
        raise ValueError(f"Unsupported AI usage type: {usage_type!r}")
    return value


def _cutoff(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current - WINDOW


def count_recent_usage(db: Session, usage_type: str, *, now: datetime | None = None) -> int:
    normalized = _normalize_usage_type(usage_type)
    return (
        db.query(AIUsageEventModel)
        .filter(
            AIUsageEventModel.usage_type == normalized,
            AIUsageEventModel.created_at >= _cutoff(now),
        )
        .count()
    )


def reserve_ai_usage(
    usage_type: str,
    *,
    limit: int,
    provider: str | None = None,
    model: str | None = None,
    task_id: str | None = None,
    now: datetime | None = None,
) -> AIUsageEventModel:
    normalized = _normalize_usage_type(usage_type)
    if limit <= 0:
        raise AIUsageLimitExceededError(f"AI {normalized} limit is disabled")

    lock = _USAGE_LOCKS[normalized]
    with lock:
        db = SessionLocal()
        try:
            current = count_recent_usage(db, normalized, now=now)
            if current >= limit:
                raise AIUsageLimitExceededError(
                    f"AI {normalized} limit exceeded: {current}/{limit} uses in the last hour"
                )
            row = AIUsageEventModel(
                usage_type=normalized,
                provider=provider,
                model=model,
                task_id=task_id,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row
        finally:
            db.close()
