import asyncio
from dataclasses import dataclass

import httpx
from _contract_helpers import configure_contract_test_db

from app.api.routes_push import list_subscriptions
from app.notifications.client import (
    send_apprise_notification,
    send_discord_notification,
    send_gotify_notification,
    send_homeassistant_notification,
    send_ntfy_notification,
    send_slack_notification,
    send_telegram_notification,
    send_web_notification,
)
from app.notifications.vapid import save_subscription
from app.services.generation.output import send_generation_notification

test_db = configure_contract_test_db("notifications")


@dataclass
class FakeResponse:
    status_code: int = 200
    json_body: object | None = None

    def json(self):
        if self.json_body is None:
            raise ValueError("not json")
        return self.json_body


class FakeAsyncClient:
    def __init__(self, *args, response: FakeResponse | None = None, **kwargs):
        self.requests = []
        self.response = response or FakeResponse()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, content=None, headers=None, json=None):
        self.requests.append({"url": url, "content": content, "headers": headers, "json": json})
        return self.response


def test_send_web_notification_returns_ok():
    result = asyncio.run(send_web_notification("Title", "Message", "Detail"))
    assert result.ok is True
    assert result.provider == "web"
    assert result.message == "Message"
    assert result.detail == "Detail"


def test_generation_notification_uses_review_token_not_app_access_token(monkeypatch):
    import app.config

    monkeypatch.setenv("APP_ACCESS_TOKEN", "full-access-token")
    monkeypatch.setenv("APP_EXTERNAL_URL", "https://dailyfx.example.test")
    app.config.get_settings.cache_clear()

    captured = {}

    async def fake_send_web_notification(**kwargs):
        captured.update(kwargs)

    preset = type(
        "NotificationPreset",
        (),
        {
            "provider": "web",
            "url": None,
            "topic": None,
            "encrypted_token": None,
            "push_subscriptions": [],
        },
    )()

    monkeypatch.setattr("app.services.generation.output.send_web_notification", fake_send_web_notification)

    asyncio.run(
        send_generation_notification(
            preset,
            title="Ready",
            summary="Generated image is ready.",
            image_url="/api/generation/history/task-review-token/image",
            task_id="task-review-token",
        )
    )

    assert "full-access-token" not in captured["url"]
    assert "review_token=" in captured["url"]
    assert "full-access-token" not in captured["detail"]
    assert "review_token=" in captured["detail"]

    monkeypatch.delenv("APP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("APP_EXTERNAL_URL", raising=False)
    app.config.get_settings.cache_clear()


def test_send_ntfy_notification_posts_to_topic(monkeypatch):
    fake_client = FakeAsyncClient(response=FakeResponse(json_body={"id": "ntfy-message-1"}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    result = asyncio.run(
        send_ntfy_notification(
            notification_url="https://ntfy.example.test",
            topic="collage",
            token="secret-token",
            title="Collage ready",
            message="Holiday",
            detail="/api/generation/results/task-123/image",
            click_url="https://dailyfx.example.test/review/task-123",
            image_url="https://dailyfx.example.test/api/generation/review/task-123/thumbnail",
        )
    )

    assert result.ok is True
    assert result.provider == "ntfy"
    assert fake_client.requests[0]["url"] == "https://ntfy.example.test/collage"
    assert fake_client.requests[0]["headers"]["Authorization"] == "Bearer secret-token"
    assert fake_client.requests[0]["headers"]["Click"] == "https://dailyfx.example.test/review/task-123"
    assert (
        fake_client.requests[0]["headers"]["Attach"]
        == "https://dailyfx.example.test/api/generation/review/task-123/thumbnail"
    )
    assert "Holiday" in fake_client.requests[0]["content"]
    assert result.detail == "https://ntfy.example.test/collage (ntfy-message-1)"


def test_send_ntfy_notification_requires_message_id(monkeypatch):
    fake_client = FakeAsyncClient(response=FakeResponse(json_body={}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    try:
        asyncio.run(
            send_ntfy_notification(
                notification_url="https://ntfy.example.test",
                topic="collage",
                token="secret-token",
                title="Collage ready",
                message="Holiday",
            )
        )
    except Exception as exc:
        assert "message id" in str(exc)
    else:
        raise AssertionError("Expected ntfy response validation to fail")


def test_send_gotify_notification_posts_to_message_endpoint(monkeypatch):
    fake_client = FakeAsyncClient(response=FakeResponse(json_body={"id": 42}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    result = asyncio.run(
        send_gotify_notification(
            notification_url="https://gotify.example.test",
            token="secret-token",
            title="Collage ready",
            message="Holiday",
            detail="/api/generation/results/task-123/image",
        )
    )

    assert result.ok is True
    assert result.provider == "gotify"
    assert fake_client.requests[0]["url"] == "https://gotify.example.test/message?token=secret-token"
    assert fake_client.requests[0]["json"]["title"] == "Collage ready"
    assert "Holiday" in fake_client.requests[0]["json"]["message"]
    assert result.detail == "https://gotify.example.test/message?token=secret-token (42)"


def test_send_gotify_notification_requires_message_id(monkeypatch):
    fake_client = FakeAsyncClient(response=FakeResponse(json_body={}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    try:
        asyncio.run(
            send_gotify_notification(
                notification_url="https://gotify.example.test",
                token="secret-token",
                title="Collage ready",
                message="Holiday",
            )
        )
    except Exception as exc:
        assert "message id" in str(exc)
    else:
        raise AssertionError("Expected gotify response validation to fail")


def test_push_subscription_list_shows_device_label():
    from app.database import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        save_subscription(
            db,
            "https://push.example.test/endpoint-1",
            "p256dh-value",
            "auth-value",
            device_label="Windows Chrome",
            user_agent="Mozilla/5.0",
        )
        payload = list_subscriptions(db)

        assert payload["count"] == 1
        assert payload["subscriptions"][0]["device_label"] == "Windows Chrome"
        assert payload["subscriptions"][0]["endpoint_preview"].startswith("https://push.example")
    finally:
        db.close()


class FakeTelegramAsyncClient:
    def __init__(self, response):
        self.requests = []
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, content=None, headers=None, json=None, files=None, data=None):
        self.requests.append(
            {
                "url": url,
                "content": content,
                "headers": headers,
                "json": json,
                "files": files,
                "data": data,
            }
        )
        return self.response


def test_send_telegram_notification_text_only(monkeypatch):
    fake_response = FakeResponse(json_body={"ok": True, "result": {"message_id": 12345}})
    fake_client = FakeTelegramAsyncClient(response=fake_response)
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    result = asyncio.run(
        send_telegram_notification(
            token="bot12345",
            chat_id="chat9876",
            title="AI Gen",
            message="Image ready",
            detail="Some description",
        )
    )

    assert result.ok is True
    assert result.provider == "telegram"
    req = fake_client.requests[0]
    assert req["url"] == "https://api.telegram.org/botbot12345/sendMessage"
    assert req["json"]["chat_id"] == "chat9876"
    assert "AI Gen" in req["json"]["text"]
    assert "Image ready" in req["json"]["text"]
    assert "Some description" in req["json"]["text"]


def test_send_telegram_notification_photo_and_buttons(monkeypatch):
    fake_response = FakeResponse(json_body={"ok": True, "result": {"message_id": 12346}})
    fake_client = FakeTelegramAsyncClient(response=fake_response)
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    result = asyncio.run(
        send_telegram_notification(
            token="bot12345",
            chat_id="chat9876",
            title="AI Gen with Photo",
            message="Image generated",
            image_bytes=b"fake-png-bytes",
            task_id="task-abc",
        )
    )

    assert result.ok is True
    assert result.provider == "telegram"
    req = fake_client.requests[0]
    assert req["url"] == "https://api.telegram.org/botbot12345/sendPhoto"
    assert req["data"]["chat_id"] == "chat9876"
    assert "AI Gen with Photo" in req["data"]["caption"]
    assert req["files"]["photo"][1] == b"fake-png-bytes"

    import json

    reply_markup = json.loads(req["data"]["reply_markup"])
    buttons = reply_markup["inline_keyboard"][0]
    assert buttons[0]["text"] == "✅ Accept"
    assert buttons[0]["callback_data"] == "accept:task-abc"
    assert buttons[1]["text"] == "❌ Reject"
    assert buttons[1]["callback_data"] == "reject:task-abc"
    assert len(buttons) == 2


def test_send_telegram_notification_with_review_url(monkeypatch):
    fake_response = FakeResponse(json_body={"ok": True, "result": {"message_id": 12347}})
    fake_client = FakeTelegramAsyncClient(response=fake_response)
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    result = asyncio.run(
        send_telegram_notification(
            token="bot12345",
            chat_id="chat9876",
            title="AI Gen",
            message="Image generated",
            task_id="task-abc",
            review_url="https://example.com/review/task-abc",
        )
    )

    assert result.ok is True
    req = fake_client.requests[0]

    reply_markup = req["json"]["reply_markup"]
    buttons = reply_markup["inline_keyboard"][0]
    assert len(buttons) == 3
    assert buttons[0]["text"] == "✅ Accept"
    assert buttons[1]["text"] == "❌ Reject"
    assert buttons[2]["text"] == "🔍 Review"
    assert buttons[2]["url"] == "https://example.com/review/task-abc"


def test_telegram_bot_callback_handling(monkeypatch):
    from app.database import SessionLocal, init_db
    from app.models.generation_history import GenerationHistoryModel
    from app.workers.telegram_bot import _handle_callback_query

    init_db()
    db = SessionLocal()
    try:
        # Create a mock generation history row
        task_id = "test-task-123"
        # Delete if existing to prevent conflicts
        db.query(GenerationHistoryModel).filter_by(task_id=task_id).delete()
        db.commit()

        row = GenerationHistoryModel(
            task_id=task_id,
            generation_type="bokeh_blur",
            status="PENDING_REVIEW",
            title="Bokeh Blur Photo",
            summary="A nice blur",
            source_asset_ids="[]",
            output_path="/tmp/fake-image.png",
            image_url="/api/generation/history/test-task-123/image",
            config_json="{}",
        )
        db.add(row)
        db.commit()

        # Mock calls
        # Mock accept_generation
        accepted_tasks = []

        async def mock_accept(t_id, req, db, _):
            accepted_tasks.append(t_id)
            row = db.query(GenerationHistoryModel).filter_by(task_id=t_id).first()
            row.status = "UPLOADED"
            db.commit()

        monkeypatch.setattr("app.workers.telegram_bot.accept_generation", mock_accept)

        # Mock Telegram API requests in FakeTelegramAsyncClient
        fake_response = FakeResponse(json_body={"ok": True})
        fake_client = FakeTelegramAsyncClient(response=fake_response)

        callback_query = {
            "id": "cb123",
            "data": f"accept:{task_id}",
            "message": {"chat": {"id": 999}, "message_id": 888, "caption": "Bokeh Blur Photo", "photo": []},
        }

        # Run callback handler
        asyncio.run(_handle_callback_query(fake_client, "fake-token", callback_query))

        # Assertions
        assert task_id in accepted_tasks

        # Verify status in database was updated to UPLOADED
        db.expire_all()
        updated_row = db.query(GenerationHistoryModel).filter_by(task_id=task_id).first()
        assert updated_row.status == "UPLOADED"

        # Verify Telegram calls were made
        assert len(fake_client.requests) == 2
        # First call is answerCallbackQuery
        assert fake_client.requests[0]["url"] == "https://api.telegram.org/botfake-token/answerCallbackQuery"
        assert fake_client.requests[0]["json"]["callback_query_id"] == "cb123"
        # Second call is editMessageCaption
        assert fake_client.requests[1]["url"] == "https://api.telegram.org/botfake-token/editMessageCaption"
        assert fake_client.requests[1]["json"]["chat_id"] == 999
        assert fake_client.requests[1]["json"]["message_id"] == 888
        assert "Accepted & Uploaded" in fake_client.requests[1]["json"]["caption"]

    finally:
        db.close()


def test_send_homeassistant_notification_sends_correct_payload(monkeypatch):
    fake_client = FakeAsyncClient(response=FakeResponse(json_body={"status": "ok"}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    result = asyncio.run(
        send_homeassistant_notification(
            notification_url="https://homeassistant.local:8123",
            token="ha-token-xyz",
            topic="mobile_app_iphone",
            title="Collage ready",
            message="Holiday",
            detail="Review here",
        )
    )

    assert result.ok is True
    assert result.provider == "homeassistant"
    req = fake_client.requests[0]
    assert req["url"] == "https://homeassistant.local:8123/api/services/notify/mobile_app_iphone"
    assert req["headers"]["Authorization"] == "Bearer ha-token-xyz"
    assert req["json"]["title"] == "Collage ready"
    assert req["json"]["message"] == "Holiday\nReview here"


def test_send_homeassistant_notification_defaults_to_notify(monkeypatch):
    fake_client = FakeAsyncClient(response=FakeResponse(json_body={"status": "ok"}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    result = asyncio.run(
        send_homeassistant_notification(
            notification_url="https://homeassistant.local:8123",
            token="ha-token-xyz",
            topic=None,
            title="Collage ready",
            message="Holiday",
        )
    )

    assert result.ok is True
    assert fake_client.requests[0]["url"] == "https://homeassistant.local:8123/api/services/notify/notify"


def test_send_apprise_notification(monkeypatch):
    class FakeApprise:
        def __init__(self):
            self.added_urls = []
            self.send_called_with = None

        def add(self, url):
            self.added_urls.append(url)

        def send(self, body, title, attach=None):
            self.send_called_with = {"body": body, "title": title, "attach": attach}
            return True

    import apprise

    monkeypatch.setattr(apprise, "Apprise", FakeApprise)

    result = asyncio.run(
        send_apprise_notification(
            notification_url="pover://user@token, tgram://bot/chat",
            title="Apprise Test",
            message="Test Msg",
            detail="Detail Info",
            image_path="/tmp/test.png",
        )
    )

    assert result.ok is True
    assert result.provider == "apprise"
    assert "Sent to 2 Apprise" in result.detail


def test_send_discord_notification(monkeypatch):
    fake_client = FakeAsyncClient(response=FakeResponse(json_body={"status": "ok"}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    result = asyncio.run(
        send_discord_notification(
            webhook_url="https://discord.com/api/webhooks/123/abc",
            title="Generation ready",
            message="Holiday",
            detail="Beautiful collage",
            click_url="https://dailyfx.local/review",
            image_url="https://dailyfx.local/thumbnail.png",
        )
    )

    assert result.ok is True
    assert result.provider == "discord"
    assert fake_client.requests[0]["url"] == "https://discord.com/api/webhooks/123/abc"
    json_data = fake_client.requests[0]["json"]
    assert len(json_data["embeds"]) == 1
    embed = json_data["embeds"][0]
    assert embed["title"] == "Generation ready"
    assert embed["description"] == "Holiday\n\nBeautiful collage"
    assert embed["url"] == "https://dailyfx.local/review"
    assert embed["image"]["url"] == "https://dailyfx.local/thumbnail.png"


def test_send_slack_notification(monkeypatch):
    fake_client = FakeAsyncClient(response=FakeResponse(json_body={"status": "ok"}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    result = asyncio.run(
        send_slack_notification(
            webhook_url="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
            title="Generation ready",
            message="Holiday",
            detail="Beautiful collage",
            click_url="https://dailyfx.local/review",
            image_url="https://dailyfx.local/thumbnail.png",
        )
    )

    assert result.ok is True
    assert result.provider == "slack"
    assert (
        fake_client.requests[0]["url"]
        == "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
    )
    json_data = fake_client.requests[0]["json"]
    assert "Generation ready" in json_data["text"]
    assert len(json_data["blocks"]) == 4
    assert json_data["blocks"][0]["text"]["text"] == "*Generation ready*\nHoliday"
    assert json_data["blocks"][1]["text"]["text"] == "Beautiful collage"
    assert json_data["blocks"][2]["image_url"] == "https://dailyfx.local/thumbnail.png"
    assert json_data["blocks"][3]["elements"][0]["url"] == "https://dailyfx.local/review"


def test_send_targeted_web_notifications(monkeypatch):
    from app.database import SessionLocal, init_db
    from app.models.push import PushSubscriptionModel
    from app.notifications.vapid import send_push_to_all

    init_db()
    db = SessionLocal()
    try:
        db.query(PushSubscriptionModel).delete()
        db.commit()

        sub1 = PushSubscriptionModel(endpoint="https://push.example/t1", p256dh="p1", auth="a1", device_label="Dev 1")
        sub2 = PushSubscriptionModel(endpoint="https://push.example/t2", p256dh="p2", auth="a2", device_label="Dev 2")
        db.add_all([sub1, sub2])
        db.commit()

        sent_endpoints = []

        def fake_webpush(subscription_info, data, vapid_private_key, vapid_claims):
            sent_endpoints.append(subscription_info["endpoint"])
            return {}

        import pywebpush

        monkeypatch.setattr(pywebpush, "webpush", fake_webpush)

        asyncio.run(send_push_to_all(db, "Title", "Body", subscription_ids=[sub1.id]))

        assert sent_endpoints == ["https://push.example/t1"]
    finally:
        db.close()


def test_web_notifications_do_not_send_without_explicit_targets(monkeypatch):
    from app.database import SessionLocal, init_db
    from app.models.push import PushSubscriptionModel
    from app.notifications.vapid import send_push_to_all

    init_db()
    db = SessionLocal()
    try:
        db.query(PushSubscriptionModel).delete()
        db.commit()

        sub = PushSubscriptionModel(endpoint="https://push.example/all", p256dh="p1", auth="a1", device_label="Dev")
        db.add(sub)
        db.commit()

        sent_endpoints = []

        def fake_webpush(subscription_info, data, vapid_private_key, vapid_claims):
            sent_endpoints.append(subscription_info["endpoint"])
            return {}

        import pywebpush

        monkeypatch.setattr(pywebpush, "webpush", fake_webpush)

        asyncio.run(send_push_to_all(db, "Title", "Body", subscription_ids=None))
        asyncio.run(send_push_to_all(db, "Title", "Body", subscription_ids=[]))

        assert sent_endpoints == []
    finally:
        db.close()


def test_test_subscription_endpoint_targets_one_subscription(monkeypatch):
    from fastapi.testclient import TestClient

    from app.database import SessionLocal, init_db
    from app.main import app
    from app.models.push import PushSubscriptionModel

    init_db()
    db = SessionLocal()
    try:
        db.query(PushSubscriptionModel).delete()
        db.commit()

        sub = PushSubscriptionModel(
            endpoint="https://push.example/test-sub",
            p256dh="p1",
            auth="a1",
            device_label="Direct Test Device",
        )
        db.add(sub)
        db.commit()

        sent_endpoints = []

        def fake_webpush(subscription_info, data, vapid_private_key, vapid_claims):
            sent_endpoints.append(subscription_info["endpoint"])
            return {}

        import pywebpush

        monkeypatch.setattr(pywebpush, "webpush", fake_webpush)

        client = TestClient(app)
        resp = client.post(f"/api/notifications/subscriptions/{sub.id}/test")

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["subscription_id"] == sub.id
        assert sent_endpoints == ["https://push.example/test-sub"]
    finally:
        db.close()


def test_test_subscription_endpoint_returns_404_for_unknown_subscription():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post("/api/notifications/subscriptions/999999/test")
    assert resp.status_code == 404
