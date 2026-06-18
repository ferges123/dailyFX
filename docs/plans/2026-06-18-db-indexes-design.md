# Design Doc: Database Indexes for Generation Status and Schedule

## 1. Goal
Optimize database performance for querying generation history and task queues by indexing key columns used in filtering, sorting, and join operations:
- `generation_history.status`
- `generation_history.schedule_id`
- `generation_tasks.status`

Per the user's decision, suggestions to convert `ai_effects.id` to an integer PK and to add `ON DELETE CASCADE/SET NULL` on schedule presets have been declined to maintain stability and avoid massive code refactoring.

## 2. Technical Designs

### A. SQLAlchemy Model Updates
We add `index=True` to the corresponding column declarations in the SQLAlchemy models:
- **`status`** and **`schedule_id`** in [GenerationHistoryModel](file:///opt/dailyFX/backend/app/models/generation_history.py#L9)
- **`status`** in [GenerationTaskModel](file:///opt/dailyFX/backend/app/models/generation_task.py#L9)

### B. Database Migration (Alembic)
We create a new Alembic migration script in `backend/app/migrations/versions/` (e.g., `0035_add_indexes_for_status_and_schedule.py`) using `op.create_index` and `op.drop_index`.

#### Migration code:
```python
"""add indexes for status and schedule

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-18 12:55:00.000000
"""

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_index("ix_generation_history_status", "generation_history", ["status"])
    op.create_index("ix_generation_history_schedule_id", "generation_history", ["schedule_id"])
    op.create_index("ix_generation_tasks_status", "generation_tasks", ["status"])

def downgrade() -> None:
    op.drop_index("ix_generation_tasks_status", table_name="generation_tasks")
    op.drop_index("ix_generation_history_schedule_id", table_name="generation_history")
    op.drop_index("ix_generation_history_status", table_name="generation_history")
```
