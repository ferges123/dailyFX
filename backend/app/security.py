import base64
import hashlib
import hmac
import logging
import secrets
import struct
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

_bearer = HTTPBearer(auto_error=False)


def require_auth(credentials: HTTPAuthorizationCredentials | None = Security(_bearer)) -> None:
    """FastAPI dependency — enforces Bearer token auth when APP_ACCESS_TOKEN is set."""
    token = get_settings().app_access_token
    if not token:
        return  # auth disabled
    if credentials is None or not secrets.compare_digest(credentials.credentials, token):
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_review_auth(credentials: HTTPAuthorizationCredentials | None = Security(_bearer)) -> None:
    """FastAPI dependency — enforces Bearer token auth on review endpoints if configured."""
    if not get_settings().require_auth_for_review:
        return  # auth not required for reviews
    require_auth(credentials)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def create_review_token(
    task_id: str,
    *,
    now: datetime | None = None,
    ttl_seconds: int | None = None,
) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    ttl = ttl_seconds if ttl_seconds is not None else get_settings().review_token_ttl_seconds
    exp = int(current.timestamp()) + ttl

    # Binary packing
    try:
        task_uuid = uuid.UUID(task_id)
        is_uuid = True
        task_bytes = task_uuid.bytes
    except ValueError:
        is_uuid = False
        task_bytes = task_id.encode("utf-8")

    marker = b"\x01" if is_uuid else b"\x00"
    packed_exp = struct.pack("!I", exp)
    payload_bytes = marker + packed_exp + task_bytes

    payload_part = _b64url_encode(payload_bytes)
    signature = hmac.new(
        get_settings().secret_key_material.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    signature_part = _b64url_encode(signature[:8])
    return f"{payload_part}.{signature_part}"


def verify_review_token(token: str | None, task_id: str, *, now: datetime | None = None) -> bool:
    if not token or "." not in token:
        return False
    try:
        payload_part, signature_part = token.split(".", 1)
        expected_signature = hmac.new(
            get_settings().secret_key_material.encode("utf-8"),
            payload_part.encode("ascii"),
            hashlib.sha256,
        ).digest()
        expected_sig_compare = expected_signature[:8]
        supplied_signature = _b64url_decode(signature_part)
        if not hmac.compare_digest(supplied_signature, expected_sig_compare):
            return False

        payload_bytes = _b64url_decode(payload_part)
        if len(payload_bytes) < 5:
            return False

        is_uuid = payload_bytes[0] == 1
        exp = struct.unpack("!I", payload_bytes[1:5])[0]

        if is_uuid:
            if len(payload_bytes) != 21:
                return False
            decoded_task_id = str(uuid.UUID(bytes=payload_bytes[5:]))
        else:
            decoded_task_id = payload_bytes[5:].decode("utf-8")

        if decoded_task_id != task_id:
            return False
    except Exception as exc:
        logger.warning("Failed to decode review token: %s", exc)
        return False

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return int(current.timestamp()) <= exp


def authorize_review_access(
    task_id: str,
    *,
    review_token: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = None,
) -> None:
    """Allow full app auth or a short-lived signed token scoped to this task."""
    if not get_settings().require_auth_for_review:
        return

    if credentials is not None and not isinstance(credentials, HTTPAuthorizationCredentials):
        credentials = None

    app_token = get_settings().app_access_token
    if app_token and credentials is not None and secrets.compare_digest(credentials.credentials, app_token):
        return

    if verify_review_token(review_token, task_id):
        return

    raise HTTPException(status_code=401, detail="Unauthorized")


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().secret_key_material.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored secret with APP_SECRET_KEY") from exc


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "****"
    return f"{value[:3]}...{value[-4:]}"
