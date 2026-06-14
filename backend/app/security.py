import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone

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
    payload = {
        "task_id": task_id,
        "exp": int(current.timestamp()) + ttl,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _b64url_encode(payload_bytes)
    signature = hmac.new(
        get_settings().secret_key_material.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_part}.{_b64url_encode(signature)}"


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
        supplied_signature = _b64url_decode(signature_part)
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return False
        payload = json.loads(_b64url_decode(payload_part))
    except Exception:
        return False

    if not isinstance(payload, dict):
        return False
    if payload.get("task_id") != task_id:
        return False
    exp = payload.get("exp")
    if not isinstance(exp, int):
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
