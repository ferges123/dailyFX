"""VAPID key management and Web Push delivery."""

from __future__ import annotations

import base64
import json
import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.push import PushSubscriptionModel, VapidKeyModel

logger = logging.getLogger(__name__)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def get_or_create_vapid_keys(db: Session) -> VapidKeyModel:
    row = db.query(VapidKeyModel).first()
    if row:
        return row

    from cryptography.hazmat.primitives.serialization import (  # type: ignore
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )
    from py_vapid import Vapid  # type: ignore

    v = Vapid()
    v.generate_keys()

    # Store private key as DER/PKCS8 base64url — what Vapid.from_der (via from_string) expects
    private_der = v.private_key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    # Store public key as uncompressed point (65 bytes) base64url — for applicationServerKey
    public_raw = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)

    row = VapidKeyModel(
        private_key=_b64url(private_der),
        public_key=_b64url(public_raw),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_vapid_public_key_base64(db: Session) -> str:
    """Return the public key as URL-safe base64 (for applicationServerKey)."""
    row = get_or_create_vapid_keys(db)
    return row.public_key  # already stored as base64url uncompressed point


def save_subscription(
    db: Session,
    endpoint: str,
    p256dh: str,
    auth: str,
    device_label: str | None = None,
    user_agent: str | None = None,
) -> PushSubscriptionModel:
    existing = db.query(PushSubscriptionModel).filter_by(endpoint=endpoint).first()
    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
        existing.device_label = device_label or existing.device_label
        existing.user_agent = user_agent or existing.user_agent
        db.commit()
        return existing
    row = PushSubscriptionModel(
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        device_label=device_label,
        user_agent=user_agent,
    )
    db.add(row)
    db.commit()
    return row


def delete_subscription(db: Session, endpoint: str) -> None:
    db.query(PushSubscriptionModel).filter_by(endpoint=endpoint).delete()
    db.commit()


async def send_push_to_all(
    db: Session,
    title: str,
    body: str,
    url: str | None = None,
    image: str | None = None,
    subscription_ids: list[int] | None = None,
) -> None:
    import asyncio

    from pywebpush import WebPushException, webpush  # type: ignore

    if not subscription_ids:
        logger.info("Skipping web push because no explicit subscription targets were provided")
        return

    keys = get_or_create_vapid_keys(db)
    subscriptions = db.query(PushSubscriptionModel).filter(PushSubscriptionModel.id.in_(subscription_ids)).all()
    if not subscriptions:
        return

    payload_data = {"title": title, "body": body}
    if url:
        payload_data["url"] = url
    if image:
        payload_data["image"] = image

    payload = json.dumps(payload_data)

    # Pre-unpack SQLAlchemy models to prevent cross-thread session access issues
    sub_data = [
        {
            "id": sub.id,
            "endpoint": sub.endpoint,
            "p256dh": sub.p256dh,
            "auth": sub.auth,
        }
        for sub in subscriptions
    ]

    def send_single(s) -> int | None:
        try:
            webpush(
                subscription_info={"endpoint": s["endpoint"], "keys": {"p256dh": s["p256dh"], "auth": s["auth"]}},
                data=payload,
                vapid_private_key=keys.private_key,
                vapid_claims={"sub": f"mailto:{get_settings().app_contact_email}"},
            )
            return None
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None) if exc.response else None
            if status in (404, 410):
                return s["id"]
            else:
                logger.warning("Web push failed for %.40s: %s", s["endpoint"], exc)
                return None
        except Exception as exc:
            logger.warning("Web push failed with unexpected error for %.40s: %s", s["endpoint"], exc)
            return None

    tasks = [asyncio.to_thread(send_single, s) for s in sub_data]
    results = await asyncio.gather(*tasks)

    stale = [r for r in results if r is not None]

    if stale:
        db.query(PushSubscriptionModel).filter(PushSubscriptionModel.id.in_(stale)).delete(synchronize_session=False)
        db.commit()

