import importlib
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException


def test_encrypt_decrypt_and_mask(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("APP_ENV", "development")

    import app.config
    import app.security

    app.config.get_settings.cache_clear()
    importlib.reload(app.security)

    encrypted = app.security.encrypt_secret("sk-test-123456")

    assert encrypted != "sk-test-123456"
    assert app.security.decrypt_secret(encrypted) == "sk-test-123456"
    assert app.security.mask_secret("sk-test-123456") == "sk-...3456"


def test_secret_key_required_in_production(monkeypatch):
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.chdir("/tmp")

    import app.config

    app.config.get_settings.cache_clear()

    try:
        app.config.get_settings()
    except Exception as exc:
        assert "app_secret_key" in str(exc).lower() or "APP_SECRET_KEY" in str(exc)
    else:
        raise AssertionError("settings loaded without APP_SECRET_KEY")


def test_secret_key_required_for_encryption_in_development(monkeypatch):
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.chdir("/tmp")

    import app.config

    app.config.get_settings.cache_clear()

    try:
        app.config.get_settings()
    except Exception as exc:
        assert "app_secret_key" in str(exc).lower() or "APP_SECRET_KEY" in str(exc)
    else:
        raise AssertionError("settings loaded without APP_SECRET_KEY")


def test_external_url_must_be_http_or_https(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_EXTERNAL_URL", "ftp://example.com")

    import app.config

    app.config.get_settings.cache_clear()

    try:
        app.config.get_settings()
    except Exception as exc:
        assert "APP_EXTERNAL_URL must be an absolute http:// or https:// URL" in str(exc)
    else:
        raise AssertionError("settings loaded with invalid APP_EXTERNAL_URL")


def test_contact_email_must_look_like_an_email(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_CONTACT_EMAIL", "invalid email")

    import app.config

    app.config.get_settings.cache_clear()

    try:
        app.config.get_settings()
    except Exception as exc:
        assert "APP_CONTACT_EMAIL must be a valid email address" in str(exc)
    else:
        raise AssertionError("settings loaded with invalid APP_CONTACT_EMAIL")


def test_app_port_must_be_in_valid_range(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_PORT", "70000")

    import app.config

    app.config.get_settings.cache_clear()

    try:
        app.config.get_settings()
    except Exception as exc:
        assert "APP_PORT" in str(exc)
    else:
        raise AssertionError("settings loaded with invalid APP_PORT")


def test_cors_origins_must_be_http_or_https(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("CORS_ORIGINS", "https://good.example, ftp://bad.example")

    import app.config

    app.config.get_settings.cache_clear()

    try:
        app.config.get_settings()
    except Exception as exc:
        assert "CORS_ORIGINS entries must be absolute http:// or https:// origins" in str(exc)
    else:
        raise AssertionError("settings loaded with invalid CORS_ORIGINS")


def test_require_review_auth_dependency(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("APP_ENV", "development")

    import app.config
    import app.security

    app.config.get_settings.cache_clear()

    # 1. require_auth_for_review is False -> should NOT raise even if app_access_token is set
    monkeypatch.setenv("REQUIRE_AUTH_FOR_REVIEW", "False")
    monkeypatch.setenv("APP_ACCESS_TOKEN", "my-token")
    app.config.get_settings.cache_clear()

    # This should pass without raising
    app.security.require_review_auth(None)

    # 2. require_auth_for_review is True -> should raise HTTPException(401) if no credentials
    monkeypatch.setenv("REQUIRE_AUTH_FOR_REVIEW", "True")
    app.config.get_settings.cache_clear()

    try:
        app.security.require_review_auth(None)
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("require_review_auth did not raise 401 when enabled and no credentials provided")


def test_review_token_round_trip_for_task(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("APP_ENV", "development")

    import app.config
    import app.security

    app.config.get_settings.cache_clear()

    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    token = app.security.create_review_token("task-review-1", now=now, ttl_seconds=300)

    assert token
    assert len(token) < 80
    assert "{" not in app.security._b64url_decode(token.split(".")[0]).decode("utf-8")
    assert app.security.verify_review_token(token, "task-review-1", now=now + timedelta(seconds=299)) is True


def test_review_token_rejects_wrong_task(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("APP_ENV", "development")

    import app.config
    import app.security

    app.config.get_settings.cache_clear()

    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    token = app.security.create_review_token("task-review-1", now=now, ttl_seconds=300)

    assert app.security.verify_review_token(token, "task-review-2", now=now) is False


def test_review_token_rejects_expired_token(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("APP_ENV", "development")

    import app.config
    import app.security

    app.config.get_settings.cache_clear()

    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    token = app.security.create_review_token("task-review-1", now=now, ttl_seconds=300)

    assert app.security.verify_review_token(token, "task-review-1", now=now + timedelta(seconds=301)) is False
