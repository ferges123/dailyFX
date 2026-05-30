from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.push import PushSubscriptionModel
from app.notifications.vapid import (
    delete_subscription,
    get_vapid_public_key_base64,
    save_subscription,
)
from app.security import require_auth

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class PushSubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    device_label: str | None = None
    user_agent: str | None = None


@router.get("/vapid-public-key")
def vapid_public_key(db: Session = Depends(get_db), _: None = Depends(require_auth)) -> dict:
    return {"publicKey": get_vapid_public_key_base64(db)}


@router.get("/subscriptions")
def list_subscriptions(db: Session = Depends(get_db), _: None = Depends(require_auth)) -> dict:
    subs = db.query(PushSubscriptionModel).all()
    return {
        "count": len(subs),
        "subscriptions": [
            {
                "id": s.id,
                "endpoint_preview": s.endpoint[:40] + "…",
                "device_label": s.device_label,
                "user_agent": s.user_agent,
                "created_at": str(s.created_at),
            }
            for s in subs
        ],
    }


@router.delete("/subscriptions/{sub_id}", status_code=204)
def delete_subscription_by_id(sub_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)) -> None:
    row = db.query(PushSubscriptionModel).filter_by(id=sub_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")
    db.delete(row)
    db.commit()


@router.post("/subscribe", status_code=201)
def subscribe(payload: PushSubscribeRequest, db: Session = Depends(get_db), _: None = Depends(require_auth)) -> dict:
    if not payload.endpoint or not payload.p256dh or not payload.auth:
        raise HTTPException(status_code=400, detail="Missing subscription fields")
    save_subscription(
        db,
        payload.endpoint,
        payload.p256dh,
        payload.auth,
        device_label=payload.device_label,
        user_agent=payload.user_agent,
    )
    return {"ok": True}


@router.post("/unsubscribe")
def unsubscribe(payload: PushSubscribeRequest, db: Session = Depends(get_db), _: None = Depends(require_auth)) -> dict:
    delete_subscription(db, payload.endpoint)
    return {"ok": True}
