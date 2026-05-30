import asyncio
from dataclasses import dataclass

import httpx
from _contract_helpers import configure_contract_test_db

from app.api.routes_push import list_subscriptions
from app.notifications.client import (
    send_apprise_notification,
    send_gotify_notification,
    send_homeassistant_notification,
    send_ntfy_notification,
    send_telegram_notification,
    send_web_notification,
)
from app.notifications.vapid import save_subscription

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
        )
    )

    assert result.ok is True
    assert result.provider == "ntfy"
    assert fake_client.requests[0]["url"] == "https://ntfy.example.test/collage"
    assert fake_client.requests[0]["headers"]["Authorization"] == "Bearer secret-token"
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
        self.requests.append({
            "url": url,
            "content": content,
            "headers": headers,
            "json": json,
            "files": files,
            "data": data,
        })
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
    assert buttons[0]["text"] == "✅ Accept & Upload"
    assert buttons[0]["callback_data"] == "accept:task-abc"
    assert buttons[1]["text"] == "❌ Reject"
    assert buttons[1]["callback_data"] == "reject:task-abc"


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
            "message": {
                "chat": {"id": 999},
                "message_id": 888,
                "caption": "Bokeh Blur Photo",
                "photo": []
            }
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


