import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEventModel

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "private_key",
    "encrypted_immich_api_key",
    "encrypted_openai_api_key",
    "encrypted_gemini_api_key",
    "encrypted_openrouter_api_key",
    "encrypted_byteplus_api_key",
    "encrypted_xiaomi_api_key",
    "encrypted_local_ai_api_key",
    "vapid_key",
    "p256dh",
    "auth",
    "subscription",
    "prompt",
    "ai_custom_prompt",
    "custom_prompt",
    "traceback",
    "stacktrace",
    "headers",
}


def is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return any(s in key_lower for s in SENSITIVE_KEYS)


def redact_value(val: Any, key: str | None = None) -> Any:
    if isinstance(val, dict):
        return {k: redact_value(v, k) for k, v in val.items()}
    elif isinstance(val, list):
        return [redact_value(item, key) for item in val]
    elif isinstance(val, str):
        if "http" in val:
            if any(s in val.lower() for s in ["token", "key", "secret"]):
                val = re.sub(r"(?i)(\?|&)([^=]*(?:token|key|secret|auth|pass)[^=]*)=([^&]+)", r"\1\2=[REDACTED]", val)
            if key is not None and is_sensitive_key(key):
                return val
        if key is not None and is_sensitive_key(key):
            return "[REDACTED]"
        return val
    elif key is not None and is_sensitive_key(key):
        return "[REDACTED]"
    return val


def build_settings_diff(old_settings: dict[str, Any], new_settings: dict[str, Any]) -> dict[str, Any]:
    diff = {}
    all_keys = set(old_settings.keys()) | set(new_settings.keys())
    for key in all_keys:
        old_val = old_settings.get(key)
        new_val = new_settings.get(key)
        if old_val != new_val:
            if is_sensitive_key(key):
                diff[key] = {"changed": True}
            else:
                diff[key] = {"from": old_val, "to": new_val}
    return diff


def record_audit_event(
    db: Session,
    action: str,
    category: str,
    outcome: str,
    actor_type: str,
    request_id: str | None = None,
    source_ip_hash: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    task_id: str | None = None,
    schedule_id: int | None = None,
    summary: str = "",
    changes: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    error_code: str | None = None,
    occurred_at: datetime | None = None,
) -> AuditEventModel | None:
    """Records an audit event in the database.

    This function is exception-safe. If recording fails, it logs the error but does not
    throw an exception, ensuring the main application workflow is not blocked.
    """
    try:
        event_id = str(uuid.uuid4())
        event_time = occurred_at or datetime.now(timezone.utc)

        # Redact input dictionaries
        safe_changes = redact_value(changes) if changes is not None else None
        safe_metadata = redact_value(metadata) if metadata is not None else None

        changes_json = json.dumps(safe_changes) if safe_changes is not None else None
        metadata_json = json.dumps(safe_metadata) if safe_metadata is not None else None

        event = AuditEventModel(
            event_id=event_id,
            occurred_at=event_time,
            action=action,
            category=category,
            outcome=outcome,
            actor_type=actor_type,
            request_id=request_id,
            source_ip_hash=source_ip_hash,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            task_id=task_id,
            schedule_id=schedule_id,
            summary=summary,
            changes_json=changes_json,
            metadata_json=metadata_json,
            error_code=error_code,
        )

        db.add(event)
        db.commit()
        return event
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception("Failed to write audit event (request_id=%s, action=%s): %s", request_id, action, e)
        return None
