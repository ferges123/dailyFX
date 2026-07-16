from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.generation_task import GenerationTaskModel
from app.security import require_auth
from app.services.generation.queue_repository import QueueRepository

router = APIRouter(prefix="/api/queue", tags=["Queue"])


@router.get("")
def list_queue(
    status: str | None = None,
    source: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    query = db.query(GenerationTaskModel)
    if status:
        query = query.filter(GenerationTaskModel.status == status)
    if source:
        query = query.filter(GenerationTaskModel.source == source)

    total = query.count()
    items = query.order_by(GenerationTaskModel.created_at.desc()).limit(limit).offset(offset).all()

    return {
        "total": total,
        "items": [
            {
                "task_id": i.task_id,
                "status": i.status,
                "step": i.step,
                "progress": i.progress,
                "priority": i.priority,
                "attempt": i.attempt,
                "created_at": i.created_at,
            }
            for i in items
        ],
    }


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    success = QueueRepository.request_cancel(db, task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel task")
    return {"message": "Cancellation request processed"}


@router.post("/{task_id}/retry")
def retry_task(task_id: str, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    try:
        new_task = QueueRepository.retry_task(db, task_id)
        return {"message": "Task retried", "task_id": new_task.task_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
