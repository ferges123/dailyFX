from datetime import datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.generation import EffectStatsResponse, TrendDataPoint, TrendsResponse
from app.security import require_auth

router = APIRouter(prefix="/api/generation", tags=["generation"])


def _quality_label_for_rate(rating_count: int, like_rate: int | None) -> str:
    if rating_count < 3 or like_rate is None:
        return "insufficient_data"
    if like_rate >= 80:
        return "excellent"
    if like_rate >= 60:
        return "good"
    if like_rate >= 40:
        return "mixed"
    return "poor"


def _effect_stats_response(
    *,
    effect_id: str,
    title: str,
    total_runs: int,
    likes: int,
    dislikes: int,
    pending_review_runs: int,
    uploaded_runs: int,
    rejected_runs: int,
    failed_runs: int,
    last_run_at: datetime | None,
) -> EffectStatsResponse:
    rating_count = likes + dislikes
    unrated_count = max(0, total_runs - rating_count)
    like_rate = round((likes / rating_count) * 100) if rating_count else None
    quality_label = _quality_label_for_rate(rating_count, like_rate)
    quality_score = like_rate if quality_label != "insufficient_data" and like_rate is not None else 0
    return EffectStatsResponse(
        effect_id=effect_id,
        title=title,
        total_runs=total_runs,
        likes=likes,
        dislikes=dislikes,
        rating_count=rating_count,
        unrated_count=unrated_count,
        like_rate=like_rate,
        quality_score=quality_score,
        quality_label=quality_label,
        pending_review_runs=pending_review_runs,
        uploaded_runs=uploaded_runs,
        rejected_runs=rejected_runs,
        failed_runs=failed_runs,
        last_run_at=last_run_at,
    )


@router.get("/stats/effects", response_model=list[EffectStatsResponse])
def get_effect_stats(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    from app.models.effect_statistics_log import EffectStatisticsLogModel
    from app.models.generation_history import GenerationHistoryModel
    from app.services.generation.modules import MODULES

    # Backfill missing statistics logs from generation history
    missing_tasks = (
        db.query(GenerationHistoryModel.task_id, GenerationHistoryModel.generation_type)
        .outerjoin(EffectStatisticsLogModel, GenerationHistoryModel.task_id == EffectStatisticsLogModel.task_id)
        .filter(EffectStatisticsLogModel.id.is_(None))
        .all()
    )
    if missing_tasks:
        for task_id, gen_type in missing_tasks:
            db.add(EffectStatisticsLogModel(effect_id=gen_type, task_id=task_id))
        db.commit()

    # Query stats grouped by effect_id
    stats = (
        db.query(
            EffectStatisticsLogModel.effect_id,
            sa.func.count(EffectStatisticsLogModel.id).label("total_runs"),
            sa.func.sum(sa.case((EffectStatisticsLogModel.liked.is_(True), 1), else_=0)).label("likes"),
            sa.func.sum(sa.case((EffectStatisticsLogModel.liked.is_(False), 1), else_=0)).label("dislikes"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "PENDING_REVIEW", 1), else_=0)).label(
                "pending_review_runs"
            ),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "UPLOADED", 1), else_=0)).label("uploaded_runs"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "REJECTED", 1), else_=0)).label("rejected_runs"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "FAILED", 1), else_=0)).label("failed_runs"),
            sa.func.max(GenerationHistoryModel.created_at).label("last_run_at"),
        )
        .outerjoin(GenerationHistoryModel, GenerationHistoryModel.task_id == EffectStatisticsLogModel.task_id)
        .group_by(EffectStatisticsLogModel.effect_id)
        .all()
    )

    results = []
    # Merge titles from MODULES registry
    for (
        effect_id,
        total,
        likes,
        dislikes,
        pending_review_runs,
        uploaded_runs,
        rejected_runs,
        failed_runs,
        last_run_at,
    ) in stats:
        module = MODULES.get(effect_id)
        title = getattr(module, "label", effect_id) if module else effect_id
        results.append(
            _effect_stats_response(
                effect_id=effect_id,
                title=title,
                total_runs=total or 0,
                likes=likes or 0,
                dislikes=dislikes or 0,
                pending_review_runs=pending_review_runs or 0,
                uploaded_runs=uploaded_runs or 0,
                rejected_runs=rejected_runs or 0,
                failed_runs=failed_runs or 0,
                last_run_at=last_run_at,
            )
        )

    # Also add any built-in/AI effects that have 0 runs yet
    seen_effects = {row[0] for row in stats}
    for key, module in MODULES.items():
        if key not in seen_effects:
            title = getattr(module, "label", key)
            results.append(
                _effect_stats_response(
                    effect_id=key,
                    title=title,
                    total_runs=0,
                    likes=0,
                    dislikes=0,
                    pending_review_runs=0,
                    uploaded_runs=0,
                    rejected_runs=0,
                    failed_runs=0,
                    last_run_at=None,
                )
            )

    return results


@router.get("/stats/trends", response_model=TrendsResponse)
def get_stats_trends(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    from app.models.effect_statistics_log import EffectStatisticsLogModel
    from app.models.generation_history import GenerationHistoryModel

    # Get daily trends for last 30 days
    daily_query = (
        db.query(
            sa.func.date(GenerationHistoryModel.created_at).label("date"),
            sa.func.count(GenerationHistoryModel.id).label("total"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "UPLOADED", 1), else_=0)).label("accepted"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "REJECTED", 1), else_=0)).label("rejected"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "FAILED", 1), else_=0)).label("failed"),
            sa.func.sum(sa.case((EffectStatisticsLogModel.liked.is_(True), 1), else_=0)).label("likes"),
            sa.func.sum(sa.case((EffectStatisticsLogModel.liked.is_(False), 1), else_=0)).label("dislikes"),
            sa.func.sum(sa.case((GenerationHistoryModel.task_id.like("auto-%"), 1), else_=0)).label("auto"),
            sa.func.sum(sa.case((GenerationHistoryModel.task_id.like("cli-%"), 1), else_=0)).label("cli"),
            sa.func.sum(
                sa.case(
                    (
                        sa.and_(
                            sa.not_(GenerationHistoryModel.task_id.like("auto-%")),
                            sa.not_(GenerationHistoryModel.task_id.like("cli-%")),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("manual"),
        )
        .outerjoin(EffectStatisticsLogModel, GenerationHistoryModel.task_id == EffectStatisticsLogModel.task_id)
        .filter(GenerationHistoryModel.created_at >= sa.func.date("now", "-30 days"))
        .group_by(sa.func.date(GenerationHistoryModel.created_at))
        .order_by(sa.func.date(GenerationHistoryModel.created_at))
        .all()
    )

    daily = [
        TrendDataPoint(
            date=str(row.date),
            total=row.total or 0,
            accepted=row.accepted or 0,
            rejected=row.rejected or 0,
            failed=row.failed or 0,
            likes=row.likes or 0,
            dislikes=row.dislikes or 0,
            auto=row.auto or 0,
            manual=row.manual or 0,
            cli=row.cli or 0,
        )
        for row in daily_query
    ]

    # Get weekly trends for last 12 weeks
    weekly_query = (
        db.query(
            sa.func.strftime("%Y-W%W", GenerationHistoryModel.created_at).label("week"),
            sa.func.count(GenerationHistoryModel.id).label("total"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "UPLOADED", 1), else_=0)).label("accepted"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "REJECTED", 1), else_=0)).label("rejected"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "FAILED", 1), else_=0)).label("failed"),
            sa.func.sum(sa.case((EffectStatisticsLogModel.liked.is_(True), 1), else_=0)).label("likes"),
            sa.func.sum(sa.case((EffectStatisticsLogModel.liked.is_(False), 1), else_=0)).label("dislikes"),
            sa.func.sum(sa.case((GenerationHistoryModel.task_id.like("auto-%"), 1), else_=0)).label("auto"),
            sa.func.sum(sa.case((GenerationHistoryModel.task_id.like("cli-%"), 1), else_=0)).label("cli"),
            sa.func.sum(
                sa.case(
                    (
                        sa.and_(
                            sa.not_(GenerationHistoryModel.task_id.like("auto-%")),
                            sa.not_(GenerationHistoryModel.task_id.like("cli-%")),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("manual"),
        )
        .outerjoin(EffectStatisticsLogModel, GenerationHistoryModel.task_id == EffectStatisticsLogModel.task_id)
        .filter(GenerationHistoryModel.created_at >= sa.func.date("now", "-84 days"))
        .group_by(sa.func.strftime("%Y-W%W", GenerationHistoryModel.created_at))
        .order_by(sa.func.strftime("%Y-W%W", GenerationHistoryModel.created_at))
        .all()
    )

    weekly = [
        TrendDataPoint(
            date=row.week,
            total=row.total or 0,
            accepted=row.accepted or 0,
            rejected=row.rejected or 0,
            failed=row.failed or 0,
            likes=row.likes or 0,
            dislikes=row.dislikes or 0,
            auto=row.auto or 0,
            manual=row.manual or 0,
            cli=row.cli or 0,
        )
        for row in weekly_query
    ]

    return TrendsResponse(daily=daily, weekly=weekly)
