from sqlalchemy.orm import Session, selectinload

from app.models.effect_statistics_log import EffectStatisticsLogModel
from app.models.generation_history import GenerationHistoryModel
from app.schemas.generation import GenerationHistoryPage
from app.services.generation.stream import get_latest_event_id


def build_generation_history_page(
    db: Session,
    *,
    status: str | None = None,
    search: str | None = None,
    effect: str | None = None,
    liked: bool | None = None,
    schedule_id: int | None = None,
    sort: str = "newest",
    offset: int = 0,
    limit: int = 10,
) -> GenerationHistoryPage:
    q = db.query(GenerationHistoryModel)
    if status:
        q = q.filter(GenerationHistoryModel.status == status.upper())
    if effect:
        q = q.filter(GenerationHistoryModel.generation_type == effect)
    if schedule_id is not None:
        if schedule_id == -1:
            q = q.filter(GenerationHistoryModel.schedule_id.is_(None))
        else:
            q = q.filter(GenerationHistoryModel.schedule_id == schedule_id)
    if liked is not None:
        q = q.join(
            EffectStatisticsLogModel,
            GenerationHistoryModel.task_id == EffectStatisticsLogModel.task_id,
        ).filter(EffectStatisticsLogModel.liked.is_(liked))
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
    if sort == "oldest":
        q = q.order_by(GenerationHistoryModel.created_at.asc())
    else:
        q = q.order_by(GenerationHistoryModel.created_at.desc())
    total = q.count()
    items = q.options(selectinload(GenerationHistoryModel.stats_log)).offset(offset).limit(limit).all()
    return GenerationHistoryPage.from_rows(
        items,
        total=total,
        latest_event_id=get_latest_event_id(db),
    )
