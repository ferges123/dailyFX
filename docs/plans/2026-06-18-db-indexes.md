# Database Indexes for Generation Status and Schedule Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Add database indexes to `generation_history.status`, `generation_history.schedule_id`, and `generation_tasks.status` to optimize search and retrieval speeds.

**Architecture:** Mapped columns in the SQLAlchemy models will be marked as `index=True`. A new Alembic migration script will be created to execute the actual schema alterations (`op.create_index`). A test utilizing SQLAlchemy `inspect` will verify the existence of the indexes on the tables.

**Tech Stack:** Python, SQLAlchemy, Alembic, pytest

---

### Task 1: Update SQLAlchemy Models

**Files:**
- Modify: `backend/app/models/generation_history.py`
- Modify: `backend/app/models/generation_task.py`

**Step 1: Write the model modifications**

Add `index=True` to the following columns:
- `status` and `schedule_id` in `backend/app/models/generation_history.py`
- `status` in `backend/app/models/generation_task.py`

**Step 2: Commit**

```bash
git add backend/app/models/generation_history.py backend/app/models/generation_task.py
git commit -m "backend: add index=True to generation status and schedule model columns"
```

---

### Task 2: Create Alembic Migration

**Files:**
- Create: `backend/app/migrations/versions/0035_add_indexes_for_status_and_schedule.py`

**Step 1: Write the migration file**

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

**Step 2: Commit**

```bash
git add backend/app/migrations/versions/0035_add_indexes_for_status_and_schedule.py
git commit -m "backend: add alembic migration for database indexes"
```

---

### Task 3: Add Verification Test

**Files:**
- Create: `backend/tests/test_database_indexes.py`

**Step 1: Write the verification test**

```python
from sqlalchemy import inspect
from app.database import engine, init_db

def test_database_indexes():
    init_db()  # Ensure database is initialized and migrations run
    inspector = inspect(engine)
    
    # Check indexes on generation_history
    history_indexes = {idx["name"]: idx["column_names"] for idx in inspector.get_indexes("generation_history")}
    assert "ix_generation_history_status" in history_indexes
    assert history_indexes["ix_generation_history_status"] == ["status"]
    assert "ix_generation_history_schedule_id" in history_indexes
    assert history_indexes["ix_generation_history_schedule_id"] == ["schedule_id"]
    
    # Check indexes on generation_tasks
    task_indexes = {idx["name"]: idx["column_names"] for idx in inspector.get_indexes("generation_tasks")}
    assert "ix_generation_tasks_status" in task_indexes
    assert task_indexes["ix_generation_tasks_status"] == ["status"]
```

**Step 2: Run the test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_database_indexes.py`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/test_database_indexes.py
git commit -m "backend: add index verification tests"
```
