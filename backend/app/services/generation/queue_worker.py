import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.generation_task import GenerationTaskModel
from app.services.audit import record_audit_event
from app.services.generation.queue_repository import QueueRepository

logger = logging.getLogger("queue_worker")


class QueueWorkerManager:
    def __init__(self, max_concurrency: int = 2):
        self.max_concurrency = max_concurrency
        self.worker_id = f"worker-{uuid.uuid4()}"
        self._running_threads = {}

    def tick(self) -> None:
        db = SessionLocal()
        try:
            active_count = db.query(GenerationTaskModel).filter(GenerationTaskModel.status == "running").count()

            slots_available = self.max_concurrency - active_count
            for _ in range(slots_available):
                task = QueueRepository.claim_next_task(db, self.worker_id)
                if not task:
                    break
                # Uruchom pipeline w osobnym wątku
                t = threading.Thread(target=self._run_task, args=(task.task_id,))
                self._running_threads[task.task_id] = t
                t.start()
        finally:
            db.close()

    def _run_task(self, task_id: str):
        db = SessionLocal()
        try:
            task = db.get(GenerationTaskModel, task_id)
            if not task:
                return

            # Symulacja pętli aktualizacji heartbeat oraz postępu
            for progress_step in range(1, 4):
                time.sleep(0.1)  # Krótki sleep dla testów
                task = db.get(GenerationTaskModel, task_id)
                if not task:
                    break
                if task.status == "cancel_requested":
                    task.status = "cancelled"
                    task.cancelled_at = datetime.now(timezone.utc)
                    task.finished_at = datetime.now(timezone.utc)
                    db.commit()
                    record_audit_event(
                        db=db,
                        action="task_cancelled",
                        category="generation",
                        outcome="success",
                        actor_type="system",
                        target_type="task",
                        target_id=task_id,
                        task_id=task_id,
                        summary=f"Running task {task_id} gracefully cancelled",
                    )
                    return
                task.progress = float(progress_step * 33)
                task.heartbeat_at = datetime.now(timezone.utc)
                db.commit()

            # Sukces
            task = db.get(GenerationTaskModel, task_id)
            if task and task.status == "running":
                task.status = "succeeded"
                task.progress = 100.0
                task.finished_at = datetime.now(timezone.utc)
                db.commit()
                record_audit_event(
                    db=db,
                    action="task_succeeded",
                    category="generation",
                    outcome="success",
                    actor_type="system",
                    target_type="task",
                    target_id=task_id,
                    task_id=task_id,
                    summary=f"Task {task_id} completed successfully",
                )
        except Exception as e:
            logger.exception("Error running task %s", task_id)
            db.rollback()
            try:
                task = db.get(GenerationTaskModel, task_id)
                if task:
                    task.status = "failed"
                    task.error = str(e)
                    task.finished_at = datetime.now(timezone.utc)
                    db.commit()
                    record_audit_event(
                        db=db,
                        action="task_failed",
                        category="generation",
                        outcome="failure",
                        actor_type="system",
                        target_type="task",
                        target_id=task_id,
                        task_id=task_id,
                        error_code="execution_error",
                        summary=f"Task {task_id} failed: {str(e)}",
                    )
            except Exception:
                pass
        finally:
            db.close()
            self._running_threads.pop(task_id, None)

    def recover_orphaned_tasks(self, db: Session) -> None:
        now = datetime.now(timezone.utc)
        heartbeat_timeout = now - timedelta(minutes=15)

        stale_tasks = (
            db.query(GenerationTaskModel)
            .filter(GenerationTaskModel.status == "running", GenerationTaskModel.heartbeat_at < heartbeat_timeout)
            .all()
        )

        for task in stale_tasks:
            task.status = "failed"
            task.error = "Task timed out due to lost worker connection (stale heartbeat)."
            task.error_code = "worker_lost"
            task.finished_at = now
            record_audit_event(
                db=db,
                action="task_recovered",
                category="generation",
                outcome="failure",
                actor_type="system",
                target_type="task",
                target_id=task.task_id,
                task_id=task.task_id,
                error_code="worker_lost",
                summary=f"Recovered stale orphaned task {task.task_id} as failed",
            )

        db.commit()
