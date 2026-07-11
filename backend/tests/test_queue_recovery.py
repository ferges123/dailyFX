from datetime import datetime, timedelta, timezone

from app.database import SessionLocal, init_db
from app.models.generation_task import GenerationTaskModel
from app.services.generation.queue_worker import QueueWorkerManager


def test_orphaned_tasks_marked_failed_on_startup():
    init_db()
    db = SessionLocal()
    db.query(GenerationTaskModel).delete()

    # 1. Task running with stale heartbeat (20 minutes ago) -> should recover as failed
    t1 = GenerationTaskModel(
        task_id="stale", status="running", heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=20)
    )
    # 2. Task running with recent heartbeat (1 minute ago) -> should remain running
    t2 = GenerationTaskModel(
        task_id="healthy", status="running", heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    db.add_all([t1, t2])
    db.commit()

    manager = QueueWorkerManager()
    manager.recover_orphaned_tasks(db)

    db.refresh(t1)
    db.refresh(t2)
    assert t1.status == "failed"
    assert t1.error_code == "worker_lost"
    assert t2.status == "running"
    db.close()
