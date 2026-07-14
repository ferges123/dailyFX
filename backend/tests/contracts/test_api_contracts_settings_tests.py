import asyncio
from types import SimpleNamespace

from _contract_helpers import FakeSettingsRow, configure_contract_test_db

from app.api import routes_settings
from app.schemas.settings import ConnectionTestResponse

configure_contract_test_db("api_contracts_settings_tests")


def test_immich_connection_contract(monkeypatch):
    async def fake_test_connection():
        return SimpleNamespace(
            ok=True,
            server_url="https://immich.example.test",
            user_email="user@example.test",
            user_id="user-123",
            server_version="1.0.0",
        )

    fake_client = SimpleNamespace(test_connection=fake_test_connection)
    monkeypatch.setattr("app.api.routes_settings.get_or_create_settings", lambda db: FakeSettingsRow())
    monkeypatch.setattr("app.api.routes_settings.build_immich_client", lambda row: fake_client)

    response = asyncio.run(routes_settings.test_immich_connection(db=None))

    assert isinstance(response, ConnectionTestResponse)
    assert response.model_dump(mode="json") == {
        "ok": True,
        "message": "Immich connection succeeded",
        "provider": "immich",
        "detail": None,
        "model": None,
        "server_url": "https://immich.example.test",
        "user_email": "user@example.test",
        "user_id": "user-123",
        "server_version": "1.0.0",
    }


def test_http_provider_contracts(monkeypatch):
    seen = {}

    async def fake_test_http_provider(url, headers, provider):
        seen[provider] = {"url": url, "headers": headers}
        return ConnectionTestResponse(
            ok=True,
            message=f"{provider} connection succeeded",
            provider=provider,
            model=f"{provider}-model",
        )

    monkeypatch.setattr("app.api.routes_settings.get_or_create_settings", lambda db: FakeSettingsRow())
    monkeypatch.setattr("app.services.settings.connection_tests.decrypt_secret", lambda value: value)
    monkeypatch.setattr("app.services.settings.connection_tests.test_http_provider", fake_test_http_provider)
    monkeypatch.setattr("app.api.routes_settings.get_local_ai_base_url", lambda row: "https://local-ai.example.test/v1")

    responses = {
        "openai": asyncio.run(routes_settings.perform_provider_connection_test(provider="openai", db=None)),
        "gemini": asyncio.run(routes_settings.perform_provider_connection_test(provider="gemini", db=None)),
        "openrouter": asyncio.run(routes_settings.perform_provider_connection_test(provider="openrouter", db=None)),
        "byteplus": asyncio.run(routes_settings.perform_provider_connection_test(provider="byteplus", db=None)),
        "xiaomi": asyncio.run(routes_settings.perform_provider_connection_test(provider="xiaomi", db=None)),
        "local": asyncio.run(routes_settings.perform_provider_connection_test(provider="local-ai", db=None)),
    }

    assert responses["openai"].model_dump(mode="json") == {
        "ok": True,
        "message": "openai connection succeeded",
        "provider": "openai",
        "detail": None,
        "model": "openai-model",
        "server_url": None,
        "user_email": None,
        "user_id": None,
        "server_version": None,
    }
    assert responses["gemini"].model_dump(mode="json") == {
        "ok": True,
        "message": "gemini connection succeeded",
        "provider": "gemini",
        "detail": None,
        "model": "gemini-model",
        "server_url": None,
        "user_email": None,
        "user_id": None,
        "server_version": None,
    }
    assert responses["openrouter"].model_dump(mode="json") == {
        "ok": True,
        "message": "openrouter connection succeeded",
        "provider": "openrouter",
        "detail": None,
        "model": "openrouter-model",
        "server_url": None,
        "user_email": None,
        "user_id": None,
        "server_version": None,
    }
    assert responses["byteplus"].model_dump(mode="json") == {
        "ok": True,
        "message": "byteplus connection succeeded",
        "provider": "byteplus",
        "detail": None,
        "model": "byteplus-model",
        "server_url": None,
        "user_email": None,
        "user_id": None,
        "server_version": None,
    }
    assert responses["xiaomi"].model_dump(mode="json") == {
        "ok": True,
        "message": "xiaomi connection succeeded",
        "provider": "xiaomi",
        "detail": None,
        "model": "xiaomi-model",
        "server_url": None,
        "user_email": None,
        "user_id": None,
        "server_version": None,
    }
    assert responses["local"].model_dump(mode="json") == {
        "ok": True,
        "message": "local connection succeeded",
        "provider": "local",
        "detail": None,
        "model": "local-model",
        "server_url": None,
        "user_email": None,
        "user_id": None,
        "server_version": None,
    }

    assert seen["openai"]["url"] == "https://api.openai.com/v1/models"
    assert seen["gemini"]["url"] == "https://generativelanguage.googleapis.com/v1beta/models"
    assert seen["openrouter"]["url"] == "https://openrouter.ai/api/v1/models"
    assert seen["byteplus"]["url"] == "https://ark.ap-southeast.bytepluses.com/api/v3/models"
    assert seen["xiaomi"]["url"] == f"{routes_settings.XIAOMI_API_BASE_URL}/models"
    assert seen["local"]["url"] == "https://local-ai.example.test/v1/models"
