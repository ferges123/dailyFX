import base64
import hashlib
import secrets

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
