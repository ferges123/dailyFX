import pytest
from _contract_helpers import configure_contract_test_db
from sqlalchemy.orm import Session

# Configure test DB first
test_db = configure_contract_test_db("audit_service")

from app.database import init_db

# Initialize database
init_db()

from app.models.audit_event import AuditEventModel
from app.services.audit import (
    build_settings_diff,
    is_sensitive_key,
    record_audit_event,
    redact_value,
)


@pytest.fixture
def db_session():
    from app.database import get_db

    db = next(get_db())
    try:
        db.query(AuditEventModel).delete()
        db.commit()
        yield db
    finally:
        db.close()


def test_is_sensitive_key():
    assert is_sensitive_key("immich_api_key") is True
    assert is_sensitive_key("apiKey") is True
    assert is_sensitive_key("my_token_field") is True
    assert is_sensitive_key("app_secret_key") is True
    assert is_sensitive_key("custom_prompt") is True
    assert is_sensitive_key("normal_field") is False


def test_redact_value():
    data = {
        "normal_key": "some_value",
        "openai_api_key": "sk-proj-12345abcdef",
        "custom_prompt": "Tell me a joke about cats",
        "nested_dict": {
            "token": "secret-token-value",
            "nested_normal": 123,
        },
        "url_with_token": "https://example.com/webhook?token=mytokenval&other=1",
        "url_normal": "https://example.com/webhook?other=1",
        "list_val": [{"secret": "nested-secret"}, {"normal": "safe"}],
    }

    redacted = redact_value(data)

    assert redacted["normal_key"] == "some_value"
    assert redacted["openai_api_key"] == "[REDACTED]"
    assert redacted["custom_prompt"] == "[REDACTED]"
    assert redacted["nested_dict"]["token"] == "[REDACTED]"
    assert redacted["nested_dict"]["nested_normal"] == 123
    assert redacted["url_with_token"] == "https://example.com/webhook?token=[REDACTED]&other=1"
    assert redacted["url_normal"] == "https://example.com/webhook?other=1"
    assert redacted["list_val"][0]["secret"] == "[REDACTED]"
    assert redacted["list_val"][1]["normal"] == "safe"


def test_build_settings_diff():
    old_settings = {
        "debug_mode": False,
        "immich_api_key": "old-key",
        "immich_url": "http://old-url.com",
    }
    new_settings = {
        "debug_mode": True,
        "immich_api_key": "new-key",
        "immich_url": "http://new-url.com",
    }

    diff = build_settings_diff(old_settings, new_settings)

    assert diff["debug_mode"] == {"from": False, "to": True}
    assert diff["immich_url"] == {"from": "http://old-url.com", "to": "http://new-url.com"}
    assert diff["immich_api_key"] == {"changed": True}


def test_record_audit_event_success(db_session: Session):
    event = record_audit_event(
        db=db_session,
        action="generation.accepted",
        category="generation",
        outcome="success",
        actor_type="app_token",
        task_id="task-123",
        summary="Image accepted and uploaded",
        changes={"status": {"from": "pending", "to": "accepted"}},
        metadata={"uploaded_asset_id": "asset-456", "token": "sensitive"},
    )

    assert event is not None
    assert event.event_id is not None
    assert event.action == "generation.accepted"
    assert event.category == "generation"
    assert event.outcome == "success"
    assert event.actor_type == "app_token"
    assert event.task_id == "task-123"
    assert "Image accepted" in event.summary
    assert "sensitive" not in event.metadata_json
    assert "[REDACTED]" in event.metadata_json

    # Retrieve from DB
    db_event = db_session.query(AuditEventModel).filter_by(event_id=event.event_id).first()
    assert db_event is not None
    assert db_event.id is not None
    assert db_event.task_id == "task-123"


def test_record_audit_event_exception_handling(db_session: Session):
    # Mock database break
    class BrokenSession:
        def add(self, instance):
            pass

        def commit(self):
            raise Exception("DB is on fire!")

        def rollback(self):
            pass

    broken_db = BrokenSession()

    # Should not raise exception
    event = record_audit_event(
        db=broken_db,  # type: ignore
        action="settings.updated",
        category="settings",
        outcome="failure",
        actor_type="cli",
    )

    assert event is None


def test_get_actor_context():
    from fastapi import Request

    from app.config import get_settings
    from app.security import create_review_token, get_actor_context

    settings = get_settings()
    original_token = settings.app_access_token
    original_secret = settings.app_secret_key
    settings.app_access_token = "my-test-access-token"
    settings.app_secret_key = "my-test-secret"
    try:
        # 1. Bearer app token match
        scope = {
            "type": "http",
            "headers": [(b"authorization", b"Bearer my-test-access-token"), (b"x-request-id", b"req-123")],
            "client": ("127.0.0.1", 12345),
            "path": "/api/settings",
            "query_string": b"",
        }
        req = Request(scope)
        context = get_actor_context(req)
        assert context.actor_type == "app_token"
        assert context.request_id == "req-123"
        assert context.source_ip_hash is not None

        # 2. Review token verification
        token = create_review_token("task-xyz", now=None, ttl_seconds=60)
        scope_review = {
            "type": "http",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "path": "/api/generation/history/task-xyz/review",
            "query_string": f"review_token={token}".encode(),
        }
        req_review = Request(scope_review)
        req_review.scope["path_params"] = {"task_id": "task-xyz"}
        context_review = get_actor_context(req_review)
        assert context_review.actor_type == "review_token"

        # 3. Unauthenticated review
        settings.require_auth_for_review = False
        scope_unauth = {
            "type": "http",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "path": "/api/generation/history/task-xyz/review",
            "query_string": b"",
        }
        req_unauth = Request(scope_unauth)
        req_unauth.scope["path_params"] = {"task_id": "task-xyz"}
        context_unauth = get_actor_context(req_unauth)
        assert context_unauth.actor_type == "unauthenticated_review"

    finally:
        settings.app_access_token = original_token
        settings.app_secret_key = original_secret


def test_generation_api_auditing(db_session: Session):
    import shutil
    import tempfile
    from pathlib import Path

    from _contract_helpers import make_generation_history_row
    from fastapi.testclient import TestClient

    from app.main import app
    from app.database import get_db_dependency
    from app.security import require_auth

    # Mock require_auth to bypass authentication
    async def override_auth():
        return None

    app.dependency_overrides[require_auth] = override_auth

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db_dependency] = override_db
    try:
        # Create temp file so it exists on disk for accept
        temp_dir = tempfile.mkdtemp()
        temp_file = Path(temp_dir) / "test.png"
        temp_file.write_bytes(b"image data")

        # Insert a mock history row
        row = make_generation_history_row(
            task_id="task-test-audit", status="PENDING_REVIEW", output_path=str(temp_file)
        )
        db_session.add(row)
        db_session.commit()

        client = TestClient(app)

        # 1. Test like endpoint audits
        response = client.post("/api/generation/history/task-test-audit/like")
        assert response.status_code == 200

        # Verify audit event was written
        events = db_session.query(AuditEventModel).filter_by(action="generation.liked", task_id="task-test-audit").all()
        assert len(events) == 1
        assert events[0].task_id == "task-test-audit"
        assert events[0].outcome == "success"

        # 2. Test dislike endpoint audits
        response = client.post("/api/generation/history/task-test-audit/dislike")
        assert response.status_code == 200

        events = (
            db_session.query(AuditEventModel).filter_by(action="generation.unliked", task_id="task-test-audit").all()
        )
        assert len(events) == 1
        assert events[0].task_id == "task-test-audit"

        # 3. Test reject endpoint audits
        response = client.post("/api/generation/history/task-test-audit/reject")
        assert response.status_code == 200

        events = (
            db_session.query(AuditEventModel).filter_by(action="generation.rejected", task_id="task-test-audit").all()
        )
        assert len(events) == 1
        assert events[0].task_id == "task-test-audit"

        # 4. Test delete endpoint audits
        response = client.delete("/api/generation/history/rejected")
        assert response.status_code == 204

        events = (
            db_session.query(AuditEventModel)
            .filter_by(action="generation.deleted")
            .filter(AuditEventModel.summary.contains("status filter: REJECTED"))
            .all()
        )
        assert len(events) == 1
        assert events[0].summary == "Deleted 1 generation history records (status filter: REJECTED)"

        shutil.rmtree(temp_dir)
    finally:
        app.dependency_overrides.clear()


def test_config_api_auditing(db_session: Session):
    import json

    from fastapi.testclient import TestClient

    from app.main import app
    from app.models.effect_preset import EffectPresetModel
    from app.models.filter_preset import FilterPresetModel
    from app.security import require_auth

    app.dependency_overrides[require_auth] = lambda: None
    try:
        client = TestClient(app)

        # 1. Test Settings PUT Auditing
        # First check current settings to get baseline
        response = client.get("/api/settings")
        assert response.status_code == 200
        settings_data = response.json()

        # Update settings
        settings_data["ai_vision_hourly_limit"] = 999
        settings_data["openai_api_key"] = "new-key-123"

        response = client.put("/api/settings", json=settings_data)
        assert response.status_code == 200

        # Check settings updated event
        events = db_session.query(AuditEventModel).filter_by(action="settings.updated").all()
        assert len(events) == 1
        changes = json.loads(events[0].changes_json)
        assert changes["ai_vision_hourly_limit"]["to"] == 999
        assert changes["openai_api_key"]["changed"] is True

        # 2. Test Connection tested Auditing
        # Try a quick connection test
        client.post("/api/settings/test-provider/openai")
        events_conn = db_session.query(AuditEventModel).filter_by(action="settings.connection_tested").all()
        assert len(events_conn) >= 1

        # 3. Test Filter Preset CRUD Auditing
        filter_payload = {
            "name": "test-filter-preset",
            "album_ids": ["123"],
            "person_filters": [],
            "start_date": None,
            "end_date": None,
            "media_type": "all",
        }
        response = client.post("/api/presets/filters", json=filter_payload)
        assert response.status_code == 201
        fp_id = response.json()["id"]

        events_fp = db_session.query(AuditEventModel).filter_by(action="preset.created").all()
        assert any(e.metadata_json and "filter" in e.metadata_json for e in events_fp)

        # UPDATE
        filter_payload["name"] = "test-filter-preset-updated"
        response = client.put(f"/api/presets/filters/{fp_id}", json=filter_payload)
        assert response.status_code == 200

        # DELETE
        response = client.delete(f"/api/presets/filters/{fp_id}")
        assert response.status_code == 204

        events_fp_del = db_session.query(AuditEventModel).filter_by(action="preset.deleted").all()
        assert any(e.metadata_json and "filter" in e.metadata_json for e in events_fp_del)

        # 4. Test Effect Preset CRUD Auditing
        effect_payload = {"name": "test-effect-preset", "groups": {}}
        response = client.post("/api/presets/effects", json=effect_payload)
        assert response.status_code == 201
        _ = response.json()["id"]

        events_ep = db_session.query(AuditEventModel).filter_by(action="preset.created").all()
        assert any(e.metadata_json and "effect" in e.metadata_json for e in events_ep)

        # 5. Test Schedule CRUD Auditing
        fp_preset = FilterPresetModel(name="sched-fp", album_ids_json="[]", media_type="all")
        ep_preset = EffectPresetModel(name="sched-ep", groups_json="{}")
        db_session.add(fp_preset)
        db_session.add(ep_preset)
        db_session.commit()

        sched_payload = {
            "name": "test-schedule",
            "enabled": True,
            "schedule_expr": "0 0 * * *",
            "filter_preset_id": fp_preset.id,
            "effect_preset_id": ep_preset.id,
            "album_name": "Test Album",
            "notification_preset_ids": [],
        }
        response = client.post("/api/schedules", json=sched_payload)
        assert response.status_code == 201
        sched_id = response.json()["id"]

        events_sched = db_session.query(AuditEventModel).filter_by(action="schedule.created").all()
        assert len(events_sched) == 1
        assert events_sched[0].target_id == str(sched_id)

        # UPDATE schedule
        sched_payload["album_name"] = "Updated Album Name"
        response = client.put(f"/api/schedules/{sched_id}", json=sched_payload)
        assert response.status_code == 200

        events_sched_up = db_session.query(AuditEventModel).filter_by(action="schedule.updated").all()
        assert len(events_sched_up) == 1
        changes_sched = json.loads(events_sched_up[0].changes_json)
        assert changes_sched["album_name"]["to"] == "Updated Album Name"

        # DELETE schedule
        response = client.delete(f"/api/schedules/{sched_id}")
        assert response.status_code == 204

        events_sched_del = db_session.query(AuditEventModel).filter_by(action="schedule.deleted").all()
        assert len(events_sched_del) == 1

    finally:
        app.dependency_overrides.clear()


def test_audit_api_endpoints(db_session: Session):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.security import require_auth

    app.dependency_overrides[require_auth] = lambda: None
    try:
        client = TestClient(app)

        # 1. Clean existing events to have controlled test
        db_session.query(AuditEventModel).delete()
        db_session.commit()

        # Insert some mock events manually for the API test
        from app.services.audit import record_audit_event

        record_audit_event(db_session, "user.login", "auth", "success", "user", summary="User logged in")
        record_audit_event(
            db_session,
            "preset.created",
            "preset",
            "success",
            "user",
            summary="Preset created",
            target_type="preset",
            target_id="10",
        )
        record_audit_event(db_session, "settings.updated", "settings", "success", "user", summary="Settings updated")
        db_session.commit()

        # 2. Get all audit logs
        response = client.get("/api/audit")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["events"]) == 3
        assert data["events"][0]["action"] == "settings.updated"  # Order by occurred_at desc

        # 3. Filter by category
        response = client.get("/api/audit?category=auth")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["events"][0]["action"] == "user.login"

        # 4. Limit and pagination
        response = client.get("/api/audit?limit=2&offset=1")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["events"]) == 2
        assert data["events"][0]["action"] == "preset.created"

        # 5. Export JSON
        response = client.get("/api/audit/export?format=json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        assert "attachment; filename=audit-log.json" in response.headers["content-disposition"]
        export_data = response.json()
        assert len(export_data) == 3

        # 6. Export CSV
        response = client.get("/api/audit/export?format=csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "attachment; filename=audit-log.csv" in response.headers["content-disposition"]
        csv_lines = response.text.strip().split("\n")
        assert len(csv_lines) == 4  # 1 header + 3 rows
        assert "event_id,occurred_at,action" in csv_lines[0]

    finally:
        app.dependency_overrides.clear()
