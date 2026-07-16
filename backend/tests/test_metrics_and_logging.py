from app.config import AppSettings


def test_settings_has_log_json_and_defaults_to_false():
    # Clear settings cache if any
    from app.config import get_settings

    get_settings.cache_clear()

    settings = AppSettings()
    assert hasattr(settings, "log_json")
    assert settings.log_json is False


def test_json_formatter_outputs_valid_json():
    import json
    import logging

    from app.observability.logging import JSONFormatter

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test_mod.py",
        lineno=42,
        msg="Hello %s!",
        args=("world",),
        exc_info=None,
        func="test_func",
    )
    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["message"] == "Hello world!"
    assert data["logger"] == "test_logger"
    assert data["level"] == "INFO"
    assert data["module"] == "test_mod"
    assert data["function"] == "test_func"
    assert data["line"] == 42
    assert "timestamp" in data


def test_setup_logging_configures_json_logging(monkeypatch):
    import logging

    import app.config
    from app.observability.logging import JSONFormatter, setup_logging

    # Set LOG_JSON to True
    monkeypatch.setenv("LOG_JSON", "true")
    app.config.get_settings.cache_clear()

    # Clear root logger handlers to start clean
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    setup_logging()

    # Check that root logger now has our JSONFormatter handler
    handlers = root.handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0].formatter, JSONFormatter)


def test_metrics_endpoint_returns_prometheus_format():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "dailyfx_app_info" in response.text
        assert "dailyfx_generation_task_status" in response.text
        assert "dailyfx_generation_history_status" in response.text


def test_metrics_endpoint_enforces_auth_when_app_access_token_configured(monkeypatch):
    from fastapi.testclient import TestClient

    import app.config as config_module
    from app.main import app

    # Enforce APP_ACCESS_TOKEN
    monkeypatch.setenv("APP_ACCESS_TOKEN", "super-secret-metrics-token")
    config_module.get_settings.cache_clear()

    with TestClient(app) as client:
        # 1. Try unauthenticated
        response = client.get("/metrics")
        assert response.status_code == 401

        # 2. Try with wrong token
        response = client.get("/metrics", headers={"Authorization": "Bearer bad-token"})
        assert response.status_code == 401

        # 3. Try with correct token
        response = client.get("/metrics", headers={"Authorization": "Bearer super-secret-metrics-token"})
        assert response.status_code == 200
        assert "dailyfx_app_info" in response.text

    # Clear setting back
    config_module.get_settings.cache_clear()


def test_metrics_includes_database_counts(monkeypatch):
    from fastapi.testclient import TestClient

    from app.database import SessionLocal
    from app.main import app
    from app.models.generation_history import GenerationHistoryModel
    from app.models.generation_task import GenerationTaskModel

    # Seed data
    db = SessionLocal()
    try:
        # Clear existing
        db.query(GenerationTaskModel).delete()
        db.query(GenerationHistoryModel).delete()

        # Add a queued task
        task = GenerationTaskModel(task_id="task_123", status="queued")
        db.add(task)

        # Add a history entry
        history = GenerationHistoryModel(
            task_id="history_123",
            generation_type="studio",
            status="ACCEPTED",
            title="test title",
            summary="test summary",
            source_asset_ids="asset1",
            config_json="{}",
        )
        db.add(history)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/metrics")
        assert response.status_code == 200

        text = response.text
        # Verify active tasks count
        assert 'dailyfx_generation_task_status{status="queued"} 1' in text
        assert 'dailyfx_generation_task_status{status="running"} 0' in text

        # Verify history status count
        assert 'dailyfx_generation_history_status{status="accepted"} 1' in text
        assert 'dailyfx_generation_history_status{status="failed"} 0' in text

    # Cleanup seed data
    db = SessionLocal()
    try:
        db.query(GenerationTaskModel).delete()
        db.query(GenerationHistoryModel).delete()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_setup_logging_silences_httpx_and_httpcore():
    import logging

    from app.observability.logging import setup_logging

    # Set root logger to INFO
    logging.getLogger().setLevel(logging.INFO)

    # Run setup
    setup_logging()

    # Assert
    assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() == logging.WARNING


def test_scheduler_main_silences_httpx_and_httpcore(monkeypatch):
    import logging

    from app.workers.scheduler import main

    # Set root logger to INFO
    logging.getLogger().setLevel(logging.INFO)

    # Mock engine setup and asyncio run to prevent database initialization and infinite loop execution
    monkeypatch.setattr("app.database._ensure_engine", lambda: None)
    monkeypatch.setattr("asyncio.run", lambda coroutine: None)

    # Run main
    main()

    # Assert
    assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() == logging.WARNING


def test_telegram_bot_import_silences_httpx_and_httpcore():
    import logging

    # Set root logger to INFO
    logging.getLogger().setLevel(logging.INFO)

    # Reload or import telegram_bot to ensure the module-level configuration is evaluated
    import importlib

    import app.workers.telegram_bot

    importlib.reload(app.workers.telegram_bot)

    # Assert
    assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() == logging.WARNING
