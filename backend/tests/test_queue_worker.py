import pytest
from app.database import SessionLocal, init_db
from app.models.generation_task import GenerationTaskModel
from app.services.generation.queue_worker import QueueWorkerManager

def test_queue_worker_concurrency():
    init_db()
    db = SessionLocal()
    db.query(GenerationTaskModel).delete()
    # Add 3 queued tasks
    for i in range(3):
        task = GenerationTaskModel(task_id=f"concurrent-{i}", status="queued", priority="normal")
        db.add(task)
    db.commit()
    
    manager = QueueWorkerManager(max_concurrency=2)
    # Should only run 2 tasks, 1 remains queued
    manager.tick()
    
    running_count = db.query(GenerationTaskModel).filter_by(status="running").count()
    assert running_count == 2
    
    # Clean up thread states
    for thread in list(manager._running_threads.values()):
        thread.join(timeout=1.0)
    db.close()
