from unittest.mock import MagicMock

import pytest

# Initialize the test DB first before importing any app modules
from _contract_helpers import configure_contract_test_db

test_db = configure_contract_test_db("effect_statistics")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.main import app
from app.models.effect_statistics_log import EffectStatisticsLogModel
from app.security import require_auth
from app.services.generation.persistence import persist_generation_result


@pytest.fixture
def authenticated_client():
    app.dependency_overrides[require_auth] = lambda: None
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    try:
        db.query(EffectStatisticsLogModel).delete()
        from app.models.generation_history import GenerationHistoryModel

        db.query(GenerationHistoryModel).delete()
        db.commit()
        yield db
    finally:
        db.close()


def test_persist_generation_result_logs_effect(db_session: Session):
    # Setup mock artifacts and result
    result = MagicMock()
    result.generation_type = "cyanotype"
    result.source_asset_ids = ["asset_1"]
    result.config = {}

    artifacts = MagicMock()
    artifacts.final_bytes = b"fake_bytes"
    artifacts.exif_info = None
    artifacts.ai_title = "Test Title"
    artifacts.ai_summary = "Test summary text"
    artifacts.ai_provider = None
    artifacts.ai_model = None
    artifacts.ai_token_count = None
    artifacts.ai_tags = []
    artifacts.metadata_provenance = {}
    artifacts.source_asset = None

    # We mock path write bytes
    output_path = MagicMock()

    persist_generation_result(
        db=db_session,
        task_id="test_task_123",
        result=result,
        artifacts=artifacts,
        output_path=output_path,
        image_url="/fake",
        schedule_id=None,
        album_name=None,
    )

    # Check that a log is inserted
    log = db_session.query(EffectStatisticsLogModel).filter_by(task_id="test_task_123").first()
    assert log is not None
    assert log.effect_id == "cyanotype"
    assert log.liked is None


def test_like_dislike_api(authenticated_client: TestClient, db_session: Session):
    from app.models.generation_history import GenerationHistoryModel

    # Create history entry
    hist = GenerationHistoryModel(
        task_id="task_abc", generation_type="cyanotype", title="T", summary="S", source_asset_ids="[]", config_json="{}"
    )
    db_session.add(hist)

    log = EffectStatisticsLogModel(effect_id="cyanotype", task_id="task_abc", liked=None)
    db_session.add(log)
    db_session.commit()

    # POST to like
    response = authenticated_client.post("/api/generation/history/task_abc/like")
    assert response.status_code == 200
    assert response.json()["liked"] is True

    # POST to like again (toggle)
    response = authenticated_client.post("/api/generation/history/task_abc/like")
    assert response.status_code == 200
    assert response.json()["liked"] is None

    # POST to dislike
    response = authenticated_client.post("/api/generation/history/task_abc/dislike")
    assert response.status_code == 200
    assert response.json()["liked"] is False


def test_stats_api(authenticated_client: TestClient, db_session: Session):
    db_session.add(EffectStatisticsLogModel(effect_id="cyanotype", task_id="t1", liked=True))
    db_session.add(EffectStatisticsLogModel(effect_id="cyanotype", task_id="t2", liked=False))
    db_session.add(EffectStatisticsLogModel(effect_id="cyanotype", task_id="t3", liked=None))
    db_session.commit()

    response = authenticated_client.get("/api/generation/stats/effects")
    assert response.status_code == 200
    stats = response.json()
    c_stat = next(s for s in stats if s["effect_id"] == "cyanotype")
    assert c_stat["total_runs"] == 3
    assert c_stat["likes"] == 1
    assert c_stat["dislikes"] == 1
