from app.database import SessionLocal, init_db
from app.models.generation_task import GenerationTaskModel
from app.services.generation.queue_repository import QueueRepository


def test_cancel_queued_and_running_tasks():
    init_db()
    db = SessionLocal()
    db.query(GenerationTaskModel).delete()

    t_queued = GenerationTaskModel(task_id="queued-cancel", status="queued")
    t_running = GenerationTaskModel(task_id="running-cancel", status="running")
    db.add_all([t_queued, t_running])
    db.commit()

    # 1. Queued tasks cancel immediately
    success = QueueRepository.request_cancel(db, "queued-cancel")
    assert success is True
    assert db.get(GenerationTaskModel, "queued-cancel").status == "cancelled"

    # 2. Running tasks enter cancel_requested
    success = QueueRepository.request_cancel(db, "running-cancel")
    assert success is True
    assert db.get(GenerationTaskModel, "running-cancel").status == "cancel_requested"
    db.close()
