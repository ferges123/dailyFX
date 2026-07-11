import pytest
from datetime import datetime, timedelta, timezone
from app.database import SessionLocal, init_db
from app.models.generation_task import GenerationTaskModel
from app.services.generation.queue_repository import QueueRepository

def test_queue_fetching_priority_and_starvation():
    init_db()
    db = SessionLocal()
    # Clean up and add test tasks
    db.query(GenerationTaskModel).delete()
    db.commit()
    
    now = datetime.now(timezone.utc)
    # Task 1: normal priority, old (35 minutes ago - starved)
    t1 = GenerationTaskModel(task_id="starved", status="queued", priority="normal", queued_at=now - timedelta(minutes=35))
    # Task 2: high priority, recent (1 minute ago)
    t2 = GenerationTaskModel(task_id="high-recent", status="queued", priority="high", queued_at=now - timedelta(minutes=1))
    db.add_all([t1, t2])
    db.commit()
    
    # starved should be fetched first due to starvation rule overrides
    first = QueueRepository.claim_next_task(db, worker_id="worker-1")
    assert first is not None
    assert first.task_id == "starved"
    db.close()
