from datetime import datetime, timezone
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


def add_history_with_stats(
    db: Session,
    *,
    task_id: str,
    effect_id: str,
    status: str = "PENDING_REVIEW",
    liked: bool | None = None,
    created_at: datetime | None = None,
):
    from app.models.generation_history import GenerationHistoryModel

    row = GenerationHistoryModel(
        task_id=task_id,
        generation_type=effect_id,
        status=status,
        title=f"{effect_id} title",
        summary="Summary",
        source_asset_ids="[]",
        config_json="{}",
    )
    if created_at is not None:
        row.created_at = created_at
        row.updated_at = created_at
    db.add(row)
    db.add(EffectStatisticsLogModel(effect_id=effect_id, task_id=task_id, liked=liked))


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
    older = datetime(2026, 1, 2, 8, 30, tzinfo=timezone.utc)
    newer = datetime(2026, 1, 3, 9, 45, tzinfo=timezone.utc)

    add_history_with_stats(
        db_session,
        task_id="t1",
        effect_id="cyanotype",
        status="UPLOADED",
        liked=True,
        created_at=older,
    )
    add_history_with_stats(
        db_session,
        task_id="t2",
        effect_id="cyanotype",
        status="REJECTED",
        liked=False,
        created_at=newer,
    )
    add_history_with_stats(
        db_session,
        task_id="t3",
        effect_id="cyanotype",
        status="PENDING_REVIEW",
        liked=None,
        created_at=older,
    )
    db_session.commit()

    response = authenticated_client.get("/api/generation/stats/effects")
    assert response.status_code == 200
    stats = response.json()
    c_stat = next(s for s in stats if s["effect_id"] == "cyanotype")

    assert c_stat["total_runs"] == 3
    assert c_stat["likes"] == 1
    assert c_stat["dislikes"] == 1
    assert c_stat["rating_count"] == 2
    assert c_stat["unrated_count"] == 1
    assert c_stat["like_rate"] == 50
    assert c_stat["quality_score"] == 0
    assert c_stat["quality_label"] == "insufficient_data"
    assert c_stat["uploaded_runs"] == 1
    assert c_stat["rejected_runs"] == 1
    assert c_stat["pending_review_runs"] == 1
    assert c_stat["failed_runs"] == 0
    assert c_stat["last_run_at"].startswith("2026-01-03T09:45:00")


@pytest.mark.parametrize(
    ("effect_id", "likes", "dislikes", "expected_label", "expected_score"),
    [
        ("excellent_effect", 4, 1, "excellent", 80),
        ("good_effect", 3, 2, "good", 60),
        ("mixed_effect", 2, 3, "mixed", 40),
        ("poor_effect", 1, 4, "poor", 20),
    ],
)
def test_stats_api_quality_labels(
    authenticated_client: TestClient,
    db_session: Session,
    effect_id: str,
    likes: int,
    dislikes: int,
    expected_label: str,
    expected_score: int,
):
    for index in range(likes):
        add_history_with_stats(
            db_session,
            task_id=f"{effect_id}_like_{index}",
            effect_id=effect_id,
            status="UPLOADED",
            liked=True,
        )
    for index in range(dislikes):
        add_history_with_stats(
            db_session,
            task_id=f"{effect_id}_dislike_{index}",
            effect_id=effect_id,
            status="REJECTED",
            liked=False,
        )
    db_session.commit()

    response = authenticated_client.get("/api/generation/stats/effects")
    assert response.status_code == 200
    stat = next(s for s in response.json() if s["effect_id"] == effect_id)

    assert stat["rating_count"] == likes + dislikes
    assert stat["like_rate"] == expected_score
    assert stat["quality_score"] == expected_score
    assert stat["quality_label"] == expected_label


def test_stats_trends_api(authenticated_client: TestClient, db_session: Session):
    # Add one auto task
    add_history_with_stats(
        db_session,
        task_id="auto-s1-12345",
        effect_id="cyanotype",
        status="UPLOADED",
        liked=True,
    )
    # Add one cli task
    add_history_with_stats(
        db_session,
        task_id="cli-s1-12345",
        effect_id="cyanotype",
        status="UPLOADED",
        liked=True,
    )
    # Add one manual task (studio)
    add_history_with_stats(
        db_session,
        task_id="studio-12345",
        effect_id="cyanotype",
        status="UPLOADED",
        liked=True,
    )
    # Add another manual task (man- trigger)
    add_history_with_stats(
        db_session,
        task_id="man-12345",
        effect_id="cyanotype",
        status="REJECTED",
        liked=False,
    )
    db_session.commit()

    response = authenticated_client.get("/api/generation/stats/trends")
    assert response.status_code == 200
    data = response.json()
    assert "daily" in data
    assert "weekly" in data

    # Find the data points and verify auto, manual, cli counts
    daily = data["daily"]
    assert len(daily) > 0
    today_point = daily[-1]
    assert today_point["auto"] == 1
    assert today_point["cli"] == 1
    assert today_point["manual"] == 2

