from __future__ import annotations

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.ai_effect import AIEffectModel
from app.services.generation.ai_effects_seed import get_seed_order_map


def list_ai_effect_rows(db: Session | None = None) -> list[AIEffectModel]:
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        from sqlalchemy.exc import OperationalError

        try:
            rows = db.query(AIEffectModel).all()
        except OperationalError:
            return []
        seed_order = get_seed_order_map()
        rows.sort(
            key=lambda row: (
                0 if row.source == "builtin" else 1 if row.source == "custom" else 2,
                seed_order.get(row.id, 10_000_000) if row.source == "builtin" else row.title.lower(),
                row.id,
            )
        )
        return rows
    finally:
        if own_session:
            db.close()
