import pytest


def test_preflight_accepts_a_valid_writable_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("APP_ENV", "development")
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{data_dir / 'app.db'}")

    import app.config
    import app.preflight

    app.config.get_settings.cache_clear()

    app.preflight.run_preflight_checks()

    assert data_dir.exists()
    assert not (data_dir / ".dailyfx-preflight-write-test").exists()


def test_preflight_rejects_blank_secret_key(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_SECRET_KEY", "   ")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'data' / 'app.db'}")

    import app.config
    import app.preflight

    app.config.get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="APP_SECRET_KEY must not be blank"):
        app.preflight.run_preflight_checks()


def test_preflight_rejects_default_secret_key_in_production(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_SECRET_KEY", "change-me-generate-a-long-random-secret")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'data' / 'app.db'}")

    import app.config
    import app.preflight

    app.config.get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="APP_SECRET_KEY must not use the example placeholder value in production"):
        app.preflight.run_preflight_checks()


def test_preflight_allows_default_secret_key_in_development(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_SECRET_KEY", "change-me-generate-a-long-random-secret")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'data' / 'app.db'}")

    import app.config
    import app.preflight

    app.config.get_settings.cache_clear()

    # Should run fine in development environment
    app.preflight.run_preflight_checks()
