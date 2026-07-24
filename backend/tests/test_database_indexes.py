from _contract_helpers import configure_contract_test_db

# Configure test database settings before importing database modules
configure_contract_test_db("indexes")

from sqlalchemy import inspect

import app.database


def test_database_indexes():
    app.database.init_db()  # Ensure database is initialized and migrations run

    assert app.database.engine is not None, "Database engine was not initialized"
    inspector = inspect(app.database.engine)

    # Check indexes on generation_history
    history_indexes = {idx["name"]: idx["column_names"] for idx in inspector.get_indexes("generation_history")}
    assert "ix_generation_history_status" in history_indexes
    assert history_indexes["ix_generation_history_status"] == ["status"]
    assert "ix_generation_history_schedule_id" in history_indexes
    assert history_indexes["ix_generation_history_schedule_id"] == ["schedule_id"]
    assert "ix_generation_history_created_at" in history_indexes
    assert history_indexes["ix_generation_history_created_at"] == ["created_at"]

    # Check indexes on schedules
    schedule_indexes = {idx["name"]: idx["column_names"] for idx in inspector.get_indexes("schedules")}
    assert "ix_schedules_enabled" in schedule_indexes
    assert schedule_indexes["ix_schedules_enabled"] == ["enabled"]

    # Check indexes on generation_tasks
    task_indexes = {idx["name"]: idx["column_names"] for idx in inspector.get_indexes("generation_tasks")}
    assert "ix_generation_tasks_status" in task_indexes
    assert task_indexes["ix_generation_tasks_status"] == ["status"]
