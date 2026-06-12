import time
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import get_settings
from app.database import get_db
from app.models.generation_task import GenerationTaskModel
from app.models.generation_history import GenerationHistoryModel
from app.security import require_auth
from app.version import APP_VERSION

router = APIRouter(tags=["metrics"])

@router.get("/metrics", response_class=Response)
def metrics(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    app_settings = get_settings()
    
    # Query database counts for active tasks (generation_tasks) grouped by status
    task_counts = {
        "queued": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
    }
    db_task_counts = db.query(
        GenerationTaskModel.status, func.count(GenerationTaskModel.task_id)
    ).group_by(GenerationTaskModel.status).all()
    for status, count in db_task_counts:
        if status:
            task_counts[status.lower()] = count
            
    # Query database counts for historical generations (generation_history) grouped by status
    history_counts = {
        "pending_review": 0,
        "accepted": 0,
        "rejected": 0,
        "failed": 0,
    }
    db_history_counts = db.query(
        GenerationHistoryModel.status, func.count(GenerationHistoryModel.id)
    ).group_by(GenerationHistoryModel.status).all()
    for status, count in db_history_counts:
        if status:
            history_counts[status.lower()] = count

    # Scheduler heartbeat age
    scheduler_age = -1.0
    try:
        scheduler_health_path = app_settings.data_dir / "scheduler.health"
        if scheduler_health_path.exists():
            scheduler_age = float(max(0, int(time.time() - scheduler_health_path.stat().st_mtime)))
    except Exception:
        pass

    # Build Prometheus exposition text
    lines = []
    
    # 1. App Info
    lines.append("# HELP dailyfx_app_info Application metadata.")
    lines.append("# TYPE dailyfx_app_info gauge")
    lines.append(f'dailyfx_app_info{{version="{APP_VERSION}"}} 1')
    
    # 2. Generation Task Status (Active Queue)
    lines.append("# HELP dailyfx_generation_task_status Count of active/queued generation tasks by status.")
    lines.append("# TYPE dailyfx_generation_task_status gauge")
    for status, count in task_counts.items():
        lines.append(f'dailyfx_generation_task_status{{status="{status}"}} {count}')
        
    # 3. Generation History Status (Historical Generations)
    lines.append("# HELP dailyfx_generation_history_status Count of historical generation tasks by status.")
    lines.append("# TYPE dailyfx_generation_history_status gauge")
    for status, count in history_counts.items():
        lines.append(f'dailyfx_generation_history_status{{status="{status}"}} {count}')
        
    # 4. Scheduler Heartbeat Age
    lines.append("# HELP dailyfx_scheduler_heartbeat_age_seconds Time in seconds since last scheduler heartbeat.")
    lines.append("# TYPE dailyfx_scheduler_heartbeat_age_seconds gauge")
    lines.append(f"dailyfx_scheduler_heartbeat_age_seconds {scheduler_age}")

    content = "\n".join(lines) + "\n"
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")
