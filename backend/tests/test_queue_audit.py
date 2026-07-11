from app.database import SessionLocal, init_db
from app.models.audit_event import AuditEventModel
from app.models.generation_task import GenerationTaskModel
from app.services.generation.queue_repository import QueueRepository


def test_queue_cancel_writes_audit_log():
    init_db()
    db = SessionLocal()
    db.query(GenerationTaskModel).delete()
    db.query(AuditEventModel).delete()
    db.commit()

    task = GenerationTaskModel(task_id="audit-cancel-task", status="queued")
    db.add(task)
    db.commit()

    success = QueueRepository.request_cancel(db, "audit-cancel-task")
    assert success is True

    # Check that audit log has been written
    audit_logs = db.query(AuditEventModel).filter_by(task_id="audit-cancel-task").all()
    assert len(audit_logs) >= 1
    assert audit_logs[0].action == "task_cancelled"
    db.close()
