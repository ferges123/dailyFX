import asyncio
from types import SimpleNamespace

import pytest

from app.services.notifications.preset_tests import run_notification_preset_test


def test_run_notification_preset_test_dispatches_providers(monkeypatch):
    calls = []

    async def fake_sender(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("app.services.notifications.preset_tests.send_web_notification", fake_sender)
    monkeypatch.setattr("app.services.notifications.preset_tests.send_ntfy_notification", fake_sender)
    monkeypatch.setattr("app.services.notifications.preset_tests.send_gotify_notification", fake_sender)
    monkeypatch.setattr("app.services.notifications.preset_tests.send_telegram_notification", fake_sender)
    monkeypatch.setattr("app.services.notifications.preset_tests.send_homeassistant_notification", fake_sender)
    monkeypatch.setattr("app.services.notifications.preset_tests.send_apprise_notification", fake_sender)
    monkeypatch.setattr("app.services.notifications.preset_tests.decrypt_secret", lambda value: "secret-token")

    row = SimpleNamespace(
        id=1,
        provider="web,ntfy,gotify,telegram,homeassistant,apprise",
        url="https://notify.example.test",
        topic="-123456789",
        encrypted_token="encrypted-token",
    )

    results, errors = asyncio.run(run_notification_preset_test(row))

    assert results == ["web", "ntfy", "gotify", "telegram", "homeassistant", "apprise"]
    assert errors == []
    assert len(calls) == 6


def test_run_notification_preset_test_requires_providers():
    row = SimpleNamespace(
        provider="",
        url=None,
        topic=None,
        encrypted_token=None,
    )

    with pytest.raises(ValueError, match="No providers configured"):
        asyncio.run(run_notification_preset_test(row))
