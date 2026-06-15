# Telegram Review Page Link Button Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Add a "Review" button linking to the review page in Telegram notifications, and rename the "Accept & Upload" button to "Accept" for compactness.

**Architecture:** Update `send_telegram_notification` to accept an optional `review_url` parameter, append a `url` type button in the inline keyboard if provided, and pass the absolute review URL from the generation output service.

**Tech Stack:** Python, FastAPI, httpx, pytest

---

### Task 1: Update existing tests and write failing test for the Review button

**Files:**
- Modify: `backend/tests/test_notifications.py:295-301`

**Step 1: Write/update the tests**

We will update `test_send_telegram_notification_photo_and_buttons` to assert `✅ Accept` instead of `✅ Accept & Upload`.
We will also write a new test `test_send_telegram_notification_with_review_url` to test that the third button is added when `review_url` is passed, and that it is not present when omitted.

```python
# In backend/tests/test_notifications.py:
# Update existing:
    reply_markup = json.loads(req["data"]["reply_markup"])
    buttons = reply_markup["inline_keyboard"][0]
    assert buttons[0]["text"] == "✅ Accept"
    assert buttons[0]["callback_data"] == "accept:task-abc"
    assert buttons[1]["text"] == "❌ Reject"
    assert buttons[1]["callback_data"] == "reject:task-abc"
    assert len(buttons) == 2  # No review button when review_url is not passed
```

And add the new test:
```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_notifications.py::test_send_telegram_notification_photo_and_buttons backend/tests/test_notifications.py::test_send_telegram_notification_with_review_url -v`
Expected: FAIL due to button text difference ("✅ Accept" vs "✅ Accept & Upload") and missing `review_url` parameter / implementation.

**Step 3: Commit tests**

```bash
git add backend/tests/test_notifications.py
git commit -m "test: add tests for telegram notification review url and name change"
```

---

### Task 2: Implement Telegram Provider Changes

**Files:**
- Modify: `backend/app/notifications/providers/telegram.py`

**Step 1: Implement the parameter and button logic**

Modify `send_telegram_notification` function definition and the `reply_markup` inline keyboard construction.

```python
# In backend/app/notifications/providers/telegram.py:
async def send_telegram_notification(
    token: str,
    chat_id: str,
    title: str,
    message: str,
    detail: str | None = None,
    image_bytes: bytes | None = None,
    task_id: str | None = None,
    review_url: str | None = None,
) -> NotificationTestResult:
    # ...
    reply_markup = None
    if task_id:
        # Include inline buttons for Accept/Reject and optionally Review
        buttons = [
            {"text": "✅ Accept", "callback_data": f"accept:{task_id}"},
            {"text": "❌ Reject", "callback_data": f"reject:{task_id}"},
        ]
        if review_url:
            buttons.append({"text": "🔍 Review", "url": review_url})
        reply_markup = {
            "inline_keyboard": [buttons]
        }
```

**Step 2: Run tests to verify they pass**

Run: `pytest backend/tests/test_notifications.py::test_send_telegram_notification_photo_and_buttons backend/tests/test_notifications.py::test_send_telegram_notification_with_review_url -v`
Expected: PASS

**Step 3: Commit changes**

```bash
git add backend/app/notifications/providers/telegram.py
git commit -m "feat: implement telegram notification review button and Accept label change"
```

---

### Task 3: Integrate with Generation Output Notification pipeline

**Files:**
- Modify: `backend/app/services/generation/output.py`

**Step 1: Pass `review_url` in the pipeline**

Modify where `send_telegram_notification` is called to supply `review_url=abs_app_url`.

```python
# In backend/app/services/generation/output.py:
                await send_telegram_notification(
                    token=notification_token or "",
                    chat_id=notification_topic,
                    title=full_title,
                    message=title,
                    detail=summary,
                    image_bytes=image_bytes,
                    task_id=task_id,
                    review_url=abs_app_url,
                )
```

**Step 2: Run all backend tests to verify integration**

Run: `pytest backend/tests/ -v`
Expected: PASS

**Step 3: Commit changes**

```bash
git add backend/app/services/generation/output.py
git commit -m "feat: pass review_url to telegram notification in generation output"
```
