from __future__ import annotations

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.ai_effect import AIEffectModel
from app.services.generation.ai_effects_seed import (
    get_seed_manifest_entry_map,
    load_seed_effects,
    seed_effect_hash,
)


def _apply_seed_to_row(
    row: AIEffectModel,
    seed,
    *,
    seed_hash: str,
    display_group: str | None,
) -> None:
    row.title = seed.title
    row.description = seed.description
    row.display_group = display_group
    row.positive_prompt = seed.positive_prompt
    row.negative_prompt = seed.negative_prompt
    row.custom_prompt_placeholder = seed.custom_prompt_placeholder
    row.builtin_hash = seed_hash
    row.latest_builtin_hash = seed_hash
    if row.source != "builtin":
        row.source = "builtin"


def sync_builtin_ai_effects(db: Session | None = None) -> list[AIEffectModel]:
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        manifest_entries = get_seed_manifest_entry_map()
        effects = load_seed_effects()
        rows = db.query(AIEffectModel).all()
        rows_by_id = {row.id: row for row in rows}
        result: list[AIEffectModel] = []

        for effect in effects:
            manifest_entry = manifest_entries.get(effect.id)
            display_group = manifest_entry.display_group if manifest_entry else None
            hidden = manifest_entry.hidden if manifest_entry else False
            effect_hash = seed_effect_hash(effect, display_group=display_group, hidden=hidden).value
            row = rows_by_id.get(effect.id)
            if row is None:
                row = AIEffectModel(
                    id=effect.id,
                    title=effect.title,
                    description=effect.description,
                    display_group=display_group,
                    positive_prompt=effect.positive_prompt,
                    negative_prompt=effect.negative_prompt,
                    custom_prompt_placeholder=effect.custom_prompt_placeholder,
                    source="builtin",
                    enabled=True,
                    weight=effect.default_weight,
                    builtin_hash=effect_hash,
                    latest_builtin_hash=effect_hash,
                )
                db.add(row)
            elif row.source == "builtin":
                row.latest_builtin_hash = effect_hash
                if row.user_modified_at is None:
                    _apply_seed_to_row(row, effect, seed_hash=effect_hash, display_group=display_group)
            result.append(row)

        db.commit()
        for row in result:
            db.refresh(row)
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        if own_session:
            db.close()
