import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest
from _contract_helpers import configure_contract_test_db
from sqlalchemy.exc import IntegrityError

from app.api.routes_settings import (
    read_settings,
    update_settings,
)
from app.api.routes_settings import (
    test_local_ai_connection as routes_test_local_ai_connection,
)
from app.api.routes_settings import (
    test_xiaomi_connection as routes_test_xiaomi_connection,
)
from app.database import SessionLocal, init_db
from app.models.settings import SettingsModel
from app.schemas.settings import SettingsUpdate
from app.services.generation.ai_vision import XIAOMI_API_BASE_URL
from app.services.immich import get_or_create_settings

test_db = configure_contract_test_db("settings")


def test_settings_are_saved_with_masked_secrets():
    os.environ["APP_SECRET_KEY"] = "test-api-secret"
    import app.config

    app.config.get_settings.cache_clear()
    init_db()
    db = SessionLocal()
    try:
        response = update_settings(
            SettingsUpdate(
                immich_url="https://immich.example.test",
                immich_api_key="immich-secret-1234",
                openai_api_key="sk-openai-9876",
                gemini_api_key="gemini-4567",
                xiaomi_api_key="mimo-secret-2468",
                ai_vision_hourly_limit=25,
                ai_image_hourly_limit=7,
            ),
            db,
        )

        assert response.immich_url == "https://immich.example.test"
        assert response.immich_api_key_masked == "********"
        assert response.openai_api_key_masked == "********"
        assert response.xiaomi_api_key_masked == "********"
        assert response.ai_vision_hourly_limit == 25
        assert response.ai_image_hourly_limit == 7

        row = db.get(SettingsModel, 1)
        assert row is not None
        assert row.encrypted_immich_api_key != "immich-secret-1234"
        assert row.encrypted_xiaomi_api_key != "mimo-secret-2468"
        assert row.ai_vision_hourly_limit == 25
        assert row.ai_image_hourly_limit == 7

        read_response = read_settings(db)
        assert read_response.immich_api_key_masked == "********"
    finally:
        db.close()


def test_xiaomi_connection_uses_mimo_models_endpoint():
    os.environ["APP_SECRET_KEY"] = "test-api-secret"
    import app.config

    app.config.get_settings.cache_clear()
    init_db()
    db = SessionLocal()
    try:
        row = get_or_create_settings(db)
        row.encrypted_xiaomi_api_key = "encrypted"
        db.add(row)
        db.commit()

        fake_result = type(
            "FakeConnectionResult",
            (),
            {
                "ok": True,
                "message": "xiaomi connection succeeded",
                "provider": "xiaomi",
                "detail": None,
                "model": "mimo-v2.5",
                "server_url": None,
                "user_email": None,
                "user_id": None,
                "server_version": None,
            },
        )()

        with (
            patch("app.services.settings.connection_tests.decrypt_secret", return_value="mimo-secret-2468"),
            patch(
                "app.services.settings.connection_tests.test_http_provider",
                new=AsyncMock(return_value=fake_result),
            ) as mock_test,
        ):
            response = asyncio.run(routes_test_xiaomi_connection(db))

        assert response.ok is True
        assert response.provider == "xiaomi"
        assert response.message == "xiaomi connection succeeded"
        mock_test.assert_awaited_once()
        args, kwargs = mock_test.await_args
        assert args[0] == f"{XIAOMI_API_BASE_URL}/models"
        assert args[1] == {"api-key": "mimo-secret-2468"}
        assert args[2] == "xiaomi"
    finally:
        db.close()


def test_local_ai_connection_uses_configured_base_url_without_token():
    os.environ["APP_SECRET_KEY"] = "test-api-secret"
    import app.config

    app.config.get_settings.cache_clear()
    init_db()
    db = SessionLocal()
    try:
        row = get_or_create_settings(db)
        row.local_ai_base_url = "http://local-ai.example.test/v1"
        row.encrypted_local_ai_api_key = None
        db.add(row)
        db.commit()

        fake_result = type(
            "FakeConnectionResult",
            (),
            {
                "ok": True,
                "message": "local connection succeeded",
                "provider": "local",
                "detail": None,
                "model": "local-model",
                "server_url": None,
                "user_email": None,
                "user_id": None,
                "server_version": None,
            },
        )()

        with (
            patch("app.services.settings.connection_tests.decrypt_secret", return_value=None),
            patch(
                "app.services.settings.connection_tests.test_http_provider",
                new=AsyncMock(return_value=fake_result),
            ) as mock_test,
        ):
            response = asyncio.run(routes_test_local_ai_connection(db))

        assert response.ok is True
        assert response.provider == "local"
        assert response.message == "local connection succeeded"
        mock_test.assert_awaited_once()
        args, kwargs = mock_test.await_args
        assert args[0] == "http://local-ai.example.test/v1/models"
        assert args[1] == {}
        assert args[2] == "local"
    finally:
        db.close()


def test_settings_reject_invalid_immich_urls():
    with pytest.raises(ValueError, match="Immich URL must be an absolute http:// or https:// URL"):
        SettingsUpdate(
            immich_url="ftp://immich.example.test",
            ai_vision_hourly_limit=25,
            ai_image_hourly_limit=7,
        )


def test_settings_reject_invalid_favorite_albums_json():
    with pytest.raises(ValueError, match="favorite_albums_json must be valid JSON"):
        SettingsUpdate(
            favorite_albums_json="{not json}",
            ai_vision_hourly_limit=25,
            ai_image_hourly_limit=7,
        )

    with pytest.raises(ValueError, match="favorite_albums_json must be a JSON array"):
        SettingsUpdate(
            favorite_albums_json='{"album": "abc"}',
            ai_vision_hourly_limit=25,
            ai_image_hourly_limit=7,
        )


def test_settings_reject_out_of_range_ai_limits():
    with pytest.raises(ValueError, match="less than or equal to 1000"):
        SettingsUpdate(
            ai_vision_hourly_limit=1001,
            ai_image_hourly_limit=7,
        )


def test_get_or_create_settings_recovers_from_duplicate_insert():
    class FakeSession:
        def __init__(self):
            self.row = None
            self.pending = None
            self.commits = 0
            self.rollbacks = 0

        def get(self, model, pk):
            return self.row if pk == 1 else None

        def add(self, row):
            self.pending = row

        def commit(self):
            self.commits += 1
            if self.commits == 1:
                self.row = self.pending
                raise IntegrityError("insert", {}, Exception("duplicate key"))
            self.row = self.pending

        def rollback(self):
            self.rollbacks += 1
            self.pending = None

        def refresh(self, row):
            self.row = row

    db = FakeSession()

    row = get_or_create_settings(db)

    assert row is db.row
    assert db.commits == 1
    assert db.rollbacks == 1


def test_get_provider_models_success():
    os.environ["APP_SECRET_KEY"] = "test-api-secret"
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.database import SessionLocal, init_db
    from app.security import require_auth
    from app.services.immich import get_or_create_settings

    init_db()
    db = SessionLocal()
    from app.main import app

    route_require_auth = require_auth
    for route in app.routes:
        if route.path == "/api/settings/models/{provider}":
            dependant = getattr(route, "dependant", None)
            if dependant:
                for d in dependant.dependencies:
                    if d.call.__name__ == "require_auth":
                        route_require_auth = d.call
                        break
    app.dependency_overrides[route_require_auth] = lambda: None

    try:
        with (
            patch("app.api.routes_settings.decrypt_secret", return_value="gemini-secret-api-key"),
            patch("httpx.AsyncClient.get") as mock_get,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(
                return_value={
                    "models": [
                        {
                            "name": "models/gemini-2.5-flash",
                            "displayName": "Gemini 2.5 Flash",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                        {
                            "name": "models/gemini-2.5-flash-image",
                            "displayName": "Gemini 2.5 Flash Image",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                    ]
                }
            )
            mock_get.return_value = mock_response

            from fastapi.testclient import TestClient

            client = TestClient(app)

            # Debug dependency identities
            print("require_auth in test:", require_auth)
            for route in app.routes:
                if route.path == "/api/settings/models/{provider}":
                    print("Route dependencies:", [d.dependency for d in route.dependencies])
            print("app.dependency_overrides:", app.dependency_overrides)

            # Setup settings model key
            row = get_or_create_settings(db)
            row.encrypted_gemini_api_key = "encrypted"
            db.add(row)
            db.commit()

            response = client.get("/api/settings/models/gemini")
            print("RESPONSE STATUS:", response.status_code)
            print("RESPONSE TEXT:", response.text)
            assert response.status_code == 200
            data = response.json()
            assert "vision_models" in data
            assert "image_models" in data
            assert any(m["value"] == "gemini-2.5-flash" for m in data["vision_models"])
            assert not any(m["value"] == "gemini-2.5-flash-image" for m in data["vision_models"])
            assert any(m["value"] == "gemini-2.5-flash-image" for m in data["image_models"])
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_provider_models_byteplus_success():
    os.environ["APP_SECRET_KEY"] = "test-api-secret"
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.database import SessionLocal, init_db
    from app.security import require_auth
    from app.services.immich import get_or_create_settings

    init_db()
    db = SessionLocal()
    from app.main import app

    route_require_auth = require_auth
    for route in app.routes:
        if route.path == "/api/settings/models/{provider}":
            dependant = getattr(route, "dependant", None)
            if dependant:
                for d in dependant.dependencies:
                    if d.call.__name__ == "require_auth":
                        route_require_auth = d.call
                        break
    app.dependency_overrides[route_require_auth] = lambda: None

    try:
        with (
            patch("app.api.routes_settings.decrypt_secret", return_value="byteplus-secret-api-key"),
            patch("httpx.AsyncClient.get") as mock_get,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(
                return_value={
                    "data": [
                        {
                            "id": "seedream-5-0-260128",
                            "name": "SeeDream 5.0",
                            "domain": "ImageGeneration",
                            "task_type": ["ImageToImage", "TextToImage"]
                        },
                        {
                            "id": "seedream-3-0-t2i-250415",
                            "name": "Seedream 3.0",
                            "domain": "ImageGeneration",
                            "task_type": ["TextToImage"]
                        },
                        {
                            "id": "seededit-3-0-t2i-250415",
                            "name": "SeedEdit 3.0 T2I",
                            "domain": "ImageGeneration",
                            "task_type": ["TextToImage"]
                        },
                        {
                            "id": "seed-2-0-pro-260328",
                            "name": "Seed 2.0 Pro",
                            "domain": "VLM",
                            "task_type": ["VisualQuestionAnswering"]
                        }
                    ]
                }
            )
            mock_get.return_value = mock_response

            from fastapi.testclient import TestClient

            client = TestClient(app)

            # Setup settings model key
            row = get_or_create_settings(db)
            row.encrypted_byteplus_api_key = "encrypted"
            db.add(row)
            db.commit()

            response = client.get("/api/settings/models/byteplus")
            assert response.status_code == 200
            data = response.json()
            assert "vision_models" in data
            assert "image_models" in data
            # Seed 2.0 Pro is vision only
            assert any(m["value"] == "seed-2-0-pro-260328" for m in data["vision_models"])
            assert not any(m["value"] == "seed-2-0-pro-260328" for m in data["image_models"])
            # SeeDream 5.0 is image only
            assert any(m["value"] == "seedream-5-0-260128" for m in data["image_models"])
            assert not any(m["value"] == "seedream-5-0-260128" for m in data["vision_models"])
            # Text-to-image-only BytePlus models are not valid for the app's img2img flow.
            assert not any(m["value"] == "seedream-3-0-t2i-250415" for m in data["image_models"])
            assert not any(m["value"] == "seededit-3-0-t2i-250415" for m in data["image_models"])
    finally:
        app.dependency_overrides.clear()
        db.close()
