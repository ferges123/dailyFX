from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    occurred_at: datetime
    action: str
    category: str
    outcome: str
    actor_type: str
    request_id: str | None = None
    source_ip_hash: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    task_id: str | None = None
    schedule_id: int | None = None
    summary: str
    changes: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    error_code: str | None = None

    @classmethod
    def from_model(cls, row: Any) -> "AuditEventResponse":
        import json

        changes = None
        if row.changes_json:
            try:
                changes = json.loads(row.changes_json)
            except Exception:
                pass
        metadata = None
        if row.metadata_json:
            try:
                metadata = json.loads(row.metadata_json)
            except Exception:
                pass

        return cls(
            event_id=row.event_id,
            occurred_at=row.occurred_at,
            action=row.action,
            category=row.category,
            outcome=row.outcome,
            actor_type=row.actor_type,
            request_id=row.request_id,
            source_ip_hash=row.source_ip_hash,
            target_type=row.target_type,
            target_id=row.target_id,
            task_id=row.task_id,
            schedule_id=row.schedule_id,
            summary=row.summary,
            changes=changes,
            metadata=metadata,
            error_code=row.error_code,
        )


class AuditLogPage(BaseModel):
    events: list[AuditEventResponse]
    total: int
    limit: int
    offset: int
