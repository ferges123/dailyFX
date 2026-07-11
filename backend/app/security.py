import base64
import hashlib
import hmac
import logging
import secrets
import struct
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request, Security
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


BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _encode_base62(num: int) -> str:
    if num == 0:
        return BASE62_ALPHABET[0]
    arr = []
    base = len(BASE62_ALPHABET)
    while num:
        num, rem = divmod(num, base)
        arr.append(BASE62_ALPHABET[rem])
    arr.reverse()
    return "".join(arr)


def _decode_base62(string: str) -> int:
    base = len(BASE62_ALPHABET)
    num = 0
    for char in string:
        if char not in BASE62_ALPHABET:
            raise ValueError(f"Invalid character {char} in base62 string")
        num = num * base + BASE62_ALPHABET.index(char)
    return num


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

    packed_exp = struct.pack("!I", exp)
    msg = task_id.encode("utf-8") + packed_exp
    signature = hmac.new(
        get_settings().secret_key_material.encode("utf-8"),
        msg,
        hashlib.sha256,
    ).digest()
    sig_bytes = signature[:10]

    token_bytes = packed_exp + sig_bytes
    num = int.from_bytes(token_bytes, "big")
    token_str = _encode_base62(num)
    return token_str.zfill(20)


def verify_review_token(token: str | None, task_id: str, *, now: datetime | None = None) -> bool:
    if not token or len(token) != 20 or not token.isalnum():
        return False
    try:
        num = _decode_base62(token)
        token_bytes = num.to_bytes(14, "big")
        packed_exp = token_bytes[:4]
        sig_bytes = token_bytes[4:]

        msg = task_id.encode("utf-8") + packed_exp
        expected_signature = hmac.new(
            get_settings().secret_key_material.encode("utf-8"),
            msg,
            hashlib.sha256,
        ).digest()
        expected_sig_bytes = expected_signature[:10]

        if not hmac.compare_digest(sig_bytes, expected_sig_bytes):
            return False

        exp = struct.unpack("!I", packed_exp)[0]
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


from dataclasses import dataclass


@dataclass
class ActorContext:
    actor_type: str
    request_id: str | None = None
    source_ip_hash: str | None = None


def resolve_actor_context(actor_ctx) -> ActorContext:
    if not isinstance(actor_ctx, ActorContext):
        return ActorContext(actor_type="user", request_id=None, source_ip_hash=None)
    return actor_ctx


def get_actor_context(request: Request) -> ActorContext:
    app_token = get_settings().app_access_token
    auth_header = request.headers.get("authorization")
    review_token = request.query_params.get("review_token") or request.headers.get("x-review-token")
    task_id = request.path_params.get("task_id")

    # Extract correlation IDs
    request_id = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")

    # Source IP hash
    source_ip_hash = None
    if request.client and request.client.host:
        source_ip_hash = hashlib.sha256(request.client.host.encode("utf-8")).hexdigest()[:16]

    actor_type = "unknown"

    if app_token:
        # Auth is enabled
        if auth_header and auth_header.startswith("Bearer "):
            provided_token = auth_header[7:]
            if secrets.compare_digest(provided_token, app_token):
                actor_type = "app_token"
            elif review_token and task_id and verify_review_token(review_token, task_id):
                actor_type = "review_token"
        else:
            # Check review token if auth header is missing/invalid
            if review_token and task_id and verify_review_token(review_token, task_id):
                actor_type = "review_token"
            elif "review" in request.url.path:
                if not get_settings().require_auth_for_review:
                    actor_type = "unauthenticated_review"
    else:
        # Auth is disabled
        if "review" in request.url.path:
            actor_type = "unauthenticated_review"
        else:
            actor_type = "unknown"

    return ActorContext(
        actor_type=actor_type,
        request_id=request_id,
        source_ip_hash=source_ip_hash,
    )
