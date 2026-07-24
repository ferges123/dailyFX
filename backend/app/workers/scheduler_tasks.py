from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import app.database
from app.services.immich import get_or_create_settings

logger = logging.getLogger(__name__)


def _backup_database(retention_count: int | None = None) -> None:
    tmp_dst = None
    try:
        from app.config import get_settings as _get_settings

        data_dir = _get_settings().data_dir
        src = data_dir / "app.db"
        if not src.exists():
            return
        backup_dir = data_dir / "backups"
        backup_dir.mkdir(exist_ok=True)
        dst = backup_dir / f"app_{datetime.now().strftime('%Y%m%d')}.db"
        tmp_dst = backup_dir / f".{dst.name}.tmp"
        tmp_dst.unlink(missing_ok=True)

        with sqlite3.connect(src) as source, sqlite3.connect(tmp_dst) as destination:
            source.backup(destination)
            integrity = destination.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0].lower() != "ok":
                raise RuntimeError(f"SQLite backup integrity check failed: {integrity!r}")
        os.replace(tmp_dst, dst)

        if retention_count is None:
            session = app.database.SessionLocal()
            try:
                settings = get_or_create_settings(session)
                retention_count = max(1, int(getattr(settings, "retention_backup_count", 7)))
            finally:
                session.close()
        else:
            retention_count = max(1, int(retention_count))

        backups = sorted(backup_dir.glob("app_*.db"))
        for old in backups[:-retention_count]:
            old.unlink(missing_ok=True)
        logger.info("DB backup created: %s (retaining %d copies)", dst.name, retention_count)
    except Exception:
        logger.exception("DB backup failed")
    finally:
        if tmp_dst is not None:
            tmp_dst.unlink(missing_ok=True)


def _cleanup_old_results(results_dir: Path) -> None:
    """Run the configured, safe retention policy."""
    try:
        from app.services.retention import execute_retention

        session = app.database.SessionLocal()
        try:
            settings = get_or_create_settings(session)
            preview = execute_retention(session, settings, data_dir=results_dir.parent)
            logger.info(
                "Retention removed %d files and found %d old metadata records (%d bytes)",
                preview.files,
                preview.metadata,
                preview.bytes,
            )
        finally:
            session.close()
    except Exception:
        logger.exception("History/result cleanup failed")
