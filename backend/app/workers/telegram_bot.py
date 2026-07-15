import asyncio
import hashlib
import logging

import httpx

from app.api.routes_generation_actions import accept_generation, reject_generation
from app.database import SessionLocal
from app.models.generation_history import GenerationHistoryModel
from app.models.notification_preset import NotificationPresetModel
from app.schemas.generation import GenerationAcceptRequest
from app.security import decrypt_secret
from app.utils.safe_logging import redact_sensitive

logger = logging.getLogger(__name__)
# Prevent Telegram Bot token leak by silencing httpx/httpcore info logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def _get_token_id(token: str) -> str:
    """Returns a secure, non-reversible, shortened hash identifier for the bot token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


async def start_telegram_bot_listener():
    """Manager task that monitors database for active Telegram bot tokens and spawns workers."""
    logger.info("Telegram Bot updates listener manager started")
    active_polls = {}  # token -> Task

    while True:
        try:
            db = SessionLocal()
            try:
                # Find all unique decrypted tokens for presets that have 'telegram' provider
                presets = db.query(NotificationPresetModel).all()
                db_tokens = set()
                for preset in presets:
                    providers = [p.strip() for p in (preset.provider or "").split(",") if p.strip()]
                    if "telegram" in providers and preset.encrypted_token:
                        token = decrypt_secret(preset.encrypted_token)
                        if token and token.strip():
                            db_tokens.add(token.strip())
            finally:
                db.close()

            # Cancel tasks for tokens no longer in DB
            for token in list(active_polls.keys()):
                if token not in db_tokens:
                    logger.info("Stopping Telegram Bot polling task for token %s", _get_token_id(token))
                    active_polls[token].cancel()
                    del active_polls[token]

            # Start tasks for new tokens
            for token in db_tokens:
                if token not in active_polls or active_polls[token].done():
                    if token in active_polls and active_polls[token].done():
                        # Clean up failed/finished task
                        try:
                            active_polls[token].result()
                        except Exception as e:
                            logger.error(
                                "Telegram polling task for token %s failed: %s",
                                _get_token_id(token),
                                redact_sensitive(e),
                            )

                    logger.info("Starting Telegram Bot polling task for token %s", _get_token_id(token))
                    active_polls[token] = asyncio.create_task(_poll_bot_updates(token))

        except Exception as e:
            logger.error("Error in Telegram Bot listener manager: %s", redact_sensitive(e))

        await asyncio.sleep(15)  # Scan presets every 15 seconds


async def _poll_bot_updates(token: str):
    """Long polling loop for a specific Telegram Bot Token."""
    offset = 0
    async with httpx.AsyncClient(timeout=35.0) as client:
        while True:
            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                params = {"offset": offset, "timeout": 30}
                response = await client.get(url, params=params)

                if response.status_code == 404:
                    logger.error("Telegram Bot API returned 404 for token %s. Is token valid?", _get_token_id(token))
                    await asyncio.sleep(30)
                    continue
                elif response.status_code >= 400:
                    logger.warning("Telegram Bot getUpdates returned HTTP %d, retrying in 10s", response.status_code)
                    await asyncio.sleep(10)
                    continue

                data = response.json()
                if not data.get("ok"):
                    logger.error("Telegram Bot getUpdates failed: %s", data.get("description"))
                    await asyncio.sleep(10)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    if "callback_query" in update:
                        await _handle_callback_query(client, token, update["callback_query"])

            except asyncio.CancelledError:
                logger.info("Telegram Bot polling loop cancelled for token %s", _get_token_id(token))
                break
            except Exception as e:
                logger.error("Exception in Telegram Bot polling loop: %s", redact_sensitive(e))
                await asyncio.sleep(10)


async def _handle_callback_query(client: httpx.AsyncClient, token: str, callback_query: dict):
    """Processes 'accept' and 'reject' actions from Telegram Inline Buttons."""
    callback_id = callback_query["id"]
    data = callback_query.get("data", "")
    message = callback_query.get("message")

    if not message or not data:
        return

    chat_id = message["chat"]["id"]
    message_id = message["message_id"]

    if ":" not in data:
        return

    action, task_id = data.split(":", 1)
    if action not in ("accept", "reject"):
        return

    logger.info("Telegram Bot received action '%s' for task '%s'", action, task_id)

    db = SessionLocal()
    try:
        # 1. Look up the task
        row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
        if not row:
            await _answer_callback(client, token, callback_id, "Error: Task not found in database.")
            await _edit_markup_to_error(client, token, chat_id, message_id, message, "Task not found in DB")
            return

        if row.status == "UPLOADED":
            await _answer_callback(client, token, callback_id, "This image has already been accepted.")
            await _edit_message_status(client, token, chat_id, message_id, message, "✅ Already Accepted & Uploaded")
            return
        elif row.status == "REJECTED":
            await _answer_callback(client, token, callback_id, "This image has already been rejected.")
            await _edit_message_status(client, token, chat_id, message_id, message, "❌ Already Rejected")
            return
        elif row.status == "FAILED":
            await _answer_callback(client, token, callback_id, "This generation run failed.")
            await _edit_message_status(client, token, chat_id, message_id, message, "⚠️ Generation Failed")
            return

        # 2. Process action
        if action == "accept":
            await _answer_callback(client, token, callback_id, "Accepting image... uploading to Immich...")
            # Run acceptance API logic directly
            await accept_generation(task_id, GenerationAcceptRequest(), db=db, _=None)
            await _edit_message_status(client, token, chat_id, message_id, message, "✅ Accepted & Uploaded to Immich")

        elif action == "reject":
            await _answer_callback(client, token, callback_id, "Rejecting image...")
            # Run rejection API logic directly
            await reject_generation(task_id, db=db, _=None)
            await _edit_message_status(client, token, chat_id, message_id, message, "❌ Rejected")

    except Exception:
        logger.exception("Error handling Telegram Bot callback action '%s' for task '%s'", action, task_id)
        await _answer_callback(client, token, callback_id, "Wystąpił błąd")
        # Note: Do not remove buttons, so user can try again once they resolve the issue.
    finally:
        db.close()


async def _answer_callback(client: httpx.AsyncClient, token: str, callback_id: str, text: str):
    """Sends an acknowledgment to Telegram to stop the button loading spinner."""
    try:
        url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
        await client.post(url, json={"callback_query_id": callback_id, "text": text})
    except Exception as e:
        logger.warning("Failed to answer callback query: %s", redact_sensitive(e))


async def _edit_message_status(
    client: httpx.AsyncClient, token: str, chat_id: int, message_id: int, message: dict, status_text: str
):
    """Updates the message description to show final status and removes inline buttons."""
    caption = message.get("caption") or message.get("text") or ""

    # Strip any old status footer to avoid stacking them
    lines = caption.split("\n")
    cleaned_lines = [
        line for line in lines if not any(status in line for status in ("Status: ", "✅", "❌", "⏳", "⚠️"))
    ]
    new_caption = "\n".join(cleaned_lines).strip()

    # Append new status
    new_caption += f"\n\n<b>Status:</b> {status_text}"

    try:
        # Check if it was a photo or text message
        if "photo" in message:
            url = f"https://api.telegram.org/bot{token}/editMessageCaption"
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "caption": new_caption,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": []},  # removes the keyboard
            }
        else:
            url = f"https://api.telegram.org/bot{token}/editMessageText"
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": new_caption,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": []},
            }

        await client.post(url, json=payload)
    except Exception as e:
        logger.warning("Failed to update Telegram message caption: %s", redact_sensitive(e))


async def _edit_markup_to_error(
    client: httpx.AsyncClient, token: str, chat_id: int, message_id: int, message: dict, error_msg: str
):
    """Removes keyboard buttons and appends error message."""
    await _edit_message_status(client, token, chat_id, message_id, message, f"⚠️ Error ({error_msg})")
