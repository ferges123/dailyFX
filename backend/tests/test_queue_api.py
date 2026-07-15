from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models.generation_task import GenerationTaskModel


def test_queue_endpoints():
    init_db()
    db = SessionLocal()
    db.query(GenerationTaskModel).delete()

    # Dodaj przykładowe zadanie do kolejki
    task = GenerationTaskModel(task_id="api-task-1", status="queued", priority="normal")
    db.add(task)
    db.commit()
    db.close()

    client = TestClient(app)

    # 1. Test pobierania listy zadań
    response = client.get("/api/queue")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["items"][0]["task_id"] == "api-task-1"

    # 2. Test anulowania zadania przez API
    response = client.post("/api/queue/api-task-1/cancel")
    assert response.status_code == 200
    assert response.json()["message"] == "Cancellation request processed"

    # Sprawdź stan w bazie
    db = SessionLocal()
    db_task = db.get(GenerationTaskModel, "api-task-1")
    assert db_task.status == "cancelled"
    db.close()


def test_queue_endpoints_require_authentication(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("APP_ACCESS_TOKEN", "queue-test-token")
    get_settings.cache_clear()

    try:
        client = TestClient(app)

        # 1. Test list queue without auth -> 401
        response = client.get("/api/queue")
        assert response.status_code == 401

        # 2. Test cancel without auth -> 401
        response = client.post("/api/queue/some-task/cancel")
        assert response.status_code == 401

        # 3. Test retry without auth -> 401
        response = client.post("/api/queue/some-task/retry")
        assert response.status_code == 401

        # 4. Test list queue with valid auth -> should not be 401
        response = client.get("/api/queue", headers={"Authorization": "Bearer queue-test-token"})
        assert response.status_code != 401
    finally:
        get_settings.cache_clear()

