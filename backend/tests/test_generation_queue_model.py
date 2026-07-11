import pytest
from datetime import datetime, timezone
from app.models.generation_task import GenerationTaskModel
from app.database import SessionLocal, init_db

def test_extended_generation_task_columns():
    init_db()
    db = SessionLocal()
    try:
        task = GenerationTaskModel(
            task_id="test-queue-task",
            status="queued",
            source="manual",
            schedule_id=None,
            priority="normal",
            attempt=1,
            max_attempts=3,
            queued_at=datetime.now(timezone.utc),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        assert task.source == "manual"
        assert task.priority == "normal"
        assert task.attempt == 1
    finally:
        db.delete(task)
        db.commit()
        db.close()
