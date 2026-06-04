from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


def bootstrap_builtin_ai_effects() -> None:
    from app.services.generation.ai_effects_sync import sync_builtin_ai_effects

    try:
        sync_builtin_ai_effects()
    except IntegrityError:
        logger.info("Builtin AI effects bootstrap hit a concurrent insert; retrying once")
        sync_builtin_ai_effects()
