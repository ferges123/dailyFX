import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.generation_task import GenerationTaskModel
from app.services.audit import record_audit_event


class QueueRepository:
    @staticmethod
    def claim_next_task(db: Session, worker_id: str) -> GenerationTaskModel | None:
        now = datetime.now(timezone.utc)
        starvation_cutoff = now - timedelta(minutes=30)

        # Pobierz wszystkie zadania queued posortowane chronologicznie
        queued_tasks = (
            db.query(GenerationTaskModel)
            .filter(GenerationTaskModel.status == "queued")
            .order_by(GenerationTaskModel.queued_at.asc())
            .all()
        )

        if not queued_tasks:
            return None

        # Sprawdź czy jest zadanie zagłodzone (starsze niż 30 min)
        starved_task = None
        for task in queued_tasks:
            if task.queued_at and task.queued_at < starvation_cutoff:
                starved_task = task
                break

        target_task = starved_task
        if not target_task:
            # Sortuj po priorytecie (high > normal > low), a potem po queued_at
            priority_map = {"high": 3, "normal": 2, "low": 1}
            queued_tasks.sort(key=lambda x: (-priority_map.get(x.priority, 2), x.queued_at or x.created_at))
            target_task = queued_tasks[0]

        # Atomowy update na status running
        updated_rows = (
            db.query(GenerationTaskModel)
            .filter(GenerationTaskModel.task_id == target_task.task_id, GenerationTaskModel.status == "queued")
            .update(
                {"status": "running", "worker_id": worker_id, "started_at": now, "heartbeat_at": now},
                synchronize_session=False,
            )
        )

        db.commit()
        if updated_rows > 0:
            db.expire(target_task)
            claimed = db.get(GenerationTaskModel, target_task.task_id)
            if claimed:
                record_audit_event(
                    db=db,
                    action="task_started",
                    category="generation",
                    outcome="success",
                    actor_type="system",
                    target_type="task",
                    target_id=claimed.task_id,
                    task_id=claimed.task_id,
                    summary=f"Task {claimed.task_id} claimed by worker {worker_id}",
                )
            return claimed
        return None

    @staticmethod
    def request_cancel(db: Session, task_id: str) -> bool:
        task = db.get(GenerationTaskModel, task_id)
        if not task:
            return False

        now = datetime.now(timezone.utc)
        if task.status == "queued":
            task.status = "cancelled"
            task.cancelled_at = now
            task.finished_at = now
            db.commit()
            record_audit_event(
                db=db,
                action="task_cancelled",
                category="generation",
                outcome="success",
                actor_type="user",
                target_type="task",
                target_id=task.task_id,
                task_id=task.task_id,
                summary=f"Queued task {task.task_id} cancelled immediately",
            )
            return True
        elif task.status == "running":
            task.status = "cancel_requested"
            task.cancel_requested_at = now
            db.commit()
            record_audit_event(
                db=db,
                action="task_cancel_requested",
                category="generation",
                outcome="success",
                actor_type="user",
                target_type="task",
                target_id=task.task_id,
                task_id=task.task_id,
                summary=f"Cancellation requested for running task {task.task_id}",
            )
            return True
        return False

    @staticmethod
    def retry_task(db: Session, task_id: str) -> GenerationTaskModel:
        parent = db.get(GenerationTaskModel, task_id)
        if not parent or parent.status not in {"failed", "cancelled", "succeeded"}:
            raise ValueError("Task cannot be retried in its current state")

        now = datetime.now(timezone.utc)
        new_task = GenerationTaskModel(
            task_id=f"retry-{uuid.uuid4()}",
            status="queued",
            source="retry",
            priority="low",
            payload_json=parent.payload_json,
            attempt=parent.attempt + 1,
            parent_task_id=parent.task_id,
            root_task_id=parent.root_task_id or parent.task_id,
            max_attempts=parent.max_attempts,
            queued_at=now,
        )
        db.add(new_task)
        db.commit()
        record_audit_event(
            db=db,
            action="task_retried",
            category="generation",
            outcome="success",
            actor_type="user",
            target_type="task",
            target_id=new_task.task_id,
            task_id=new_task.task_id,
            summary=f"Retried task {parent.task_id} as new task {new_task.task_id}",
        )
        return new_task
