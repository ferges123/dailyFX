import pytest
from app.database import SessionLocal, init_db
from app.models.generation_task import GenerationTaskModel
from app.services.generation.queue_repository import QueueRepository

def test_task_retry_linkage():
    init_db()
    db = SessionLocal()
    db.query(GenerationTaskModel).delete()
    
    parent = GenerationTaskModel(
        task_id="failed-task",
        status="failed",
        payload_json='{"style": "claymation"}',
        attempt=1
    )
    db.add(parent)
    db.commit()
    
    new_task = QueueRepository.retry_task(db, "failed-task")
    assert new_task.attempt == 2
    assert new_task.parent_task_id == "failed-task"
    assert new_task.root_task_id == "failed-task"
    assert new_task.status == "queued"
    db.close()
