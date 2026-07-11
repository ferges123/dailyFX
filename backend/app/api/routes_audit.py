from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_event import AuditEventModel
from app.schemas.audit import AuditEventResponse, AuditLogPage
from app.security import require_auth

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=AuditLogPage)
def get_audit_logs(
    action: str | None = None,
    category: str | None = None,
    outcome: str | None = None,
    actor_type: str | None = None,
    task_id: str | None = None,
    schedule_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
) -> AuditLogPage:
    query = db.query(AuditEventModel)

    if action:
        query = query.filter(AuditEventModel.action == action)
    if category:
        query = query.filter(AuditEventModel.category == category)
    if outcome:
        query = query.filter(AuditEventModel.outcome == outcome)
    if actor_type:
        query = query.filter(AuditEventModel.actor_type == actor_type)
    if task_id:
        query = query.filter(AuditEventModel.task_id == task_id)
    if schedule_id is not None:
        query = query.filter(AuditEventModel.schedule_id == schedule_id)
    if date_from:
        query = query.filter(AuditEventModel.occurred_at >= date_from)
    if date_to:
        query = query.filter(AuditEventModel.occurred_at <= date_to)

    total = query.count()
    events = query.order_by(AuditEventModel.occurred_at.desc()).offset(offset).limit(limit).all()

    return AuditLogPage(
        events=[AuditEventResponse.from_model(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/export")
def export_audit_logs(
    format: Literal["json", "csv"] = "json",
    action: str | None = None,
    category: str | None = None,
    outcome: str | None = None,
    actor_type: str | None = None,
    task_id: str | None = None,
    schedule_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
) -> Response:
    query = db.query(AuditEventModel)

    if action:
        query = query.filter(AuditEventModel.action == action)
    if category:
        query = query.filter(AuditEventModel.category == category)
    if outcome:
        query = query.filter(AuditEventModel.outcome == outcome)
    if actor_type:
        query = query.filter(AuditEventModel.actor_type == actor_type)
    if task_id:
        query = query.filter(AuditEventModel.task_id == task_id)
    if schedule_id is not None:
        query = query.filter(AuditEventModel.schedule_id == schedule_id)
    if date_from:
        query = query.filter(AuditEventModel.occurred_at >= date_from)
    if date_to:
        query = query.filter(AuditEventModel.occurred_at <= date_to)

    results = query.order_by(AuditEventModel.occurred_at.desc()).all()

    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Headers matching the schema fields
        writer.writerow(
            [
                "event_id",
                "occurred_at",
                "action",
                "category",
                "outcome",
                "actor_type",
                "request_id",
                "source_ip_hash",
                "target_type",
                "target_id",
                "task_id",
                "schedule_id",
                "summary",
                "changes",
                "metadata",
                "error_code",
            ]
        )

        for row in results:
            writer.writerow(
                [
                    row.event_id,
                    row.occurred_at.isoformat(),
                    row.action,
                    row.category,
                    row.outcome,
                    row.actor_type,
                    row.request_id or "",
                    row.source_ip_hash or "",
                    row.target_type or "",
                    row.target_id or "",
                    row.task_id or "",
                    row.schedule_id if row.schedule_id is not None else "",
                    row.summary,
                    row.changes_json or "",
                    row.metadata_json or "",
                    row.error_code or "",
                ]
            )

        csv_data = output.getvalue()
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit-log.csv"},
        )

    else:
        import json

        from fastapi.encoders import jsonable_encoder

        events = [AuditEventResponse.from_model(e) for e in results]
        json_data = json.dumps(jsonable_encoder(events), indent=2)
        return Response(
            content=json_data,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit-log.json"},
        )
