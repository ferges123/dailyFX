from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.generation_history import GenerationHistoryModel
from app.schemas.generation import GenerationHistoryPage
from app.services.generation.stream import get_latest_event_id


def build_generation_history_page(
    db: Session,
    *,
    status: str | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 10,
) -> GenerationHistoryPage:
    q = db.query(GenerationHistoryModel).order_by(GenerationHistoryModel.created_at.desc())
    if status:
        q = q.filter(GenerationHistoryModel.status == status.upper())
    if search:
        from sqlalchemy import func as sqlfunc

        escaped_search = search.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_term = f"%{escaped_search}%"
        q = q.filter(
            (sqlfunc.lower(GenerationHistoryModel.title).like(search_term, escape="\\"))
            | (sqlfunc.lower(GenerationHistoryModel.summary).like(search_term, escape="\\"))
            | (sqlfunc.lower(GenerationHistoryModel.generation_type).like(search_term, escape="\\"))
            | (sqlfunc.lower(GenerationHistoryModel.provider).like(search_term, escape="\\"))
            | (sqlfunc.lower(GenerationHistoryModel.model).like(search_term, escape="\\"))
            | (sqlfunc.lower(GenerationHistoryModel.album_name).like(search_term, escape="\\"))
        )
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return GenerationHistoryPage.from_rows(
        items,
        total=total,
        latest_event_id=get_latest_event_id(db),
    )
