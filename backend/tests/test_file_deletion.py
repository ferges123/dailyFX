from datetime import datetime, timezone
from pathlib import Path

import pytest
from _contract_helpers import configure_contract_test_db

configure_contract_test_db("file_deletion")

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.file_deletion_job import FileDeletionJobModel  # noqa: E402
from app.services.file_deletion import process_file_deletion_jobs, queue_file_deletion  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    init_db()
    db = SessionLocal()
    try:
        db.query(FileDeletionJobModel).delete()
        db.commit()
    finally:
        db.close()
    yield


def test_file_is_deleted_only_after_outbox_commit(tmp_path: Path):
    path = tmp_path / "result.png"
    path.write_bytes(b"image")

    db = SessionLocal()
    try:
        queue_file_deletion(db, path=path, reason="test")
        db.commit()
        assert path.exists()

        deleted, failed = process_file_deletion_jobs(db, data_dir=tmp_path)

        assert (deleted, failed) == (1, 0)
        assert not path.exists()
        job = db.query(FileDeletionJobModel).one()
        assert job.status == "completed"
    finally:
        db.close()


def test_rollback_leaves_file_and_does_not_persist_job(tmp_path: Path):
    path = tmp_path / "result.png"
    path.write_bytes(b"image")

    db = SessionLocal()
    try:
        queue_file_deletion(db, path=path, reason="test")
        db.rollback()
        assert path.exists()
        assert db.query(FileDeletionJobModel).count() == 0
    finally:
        db.close()


def test_failed_unlink_is_retryable(monkeypatch, tmp_path: Path):
    path = tmp_path / "result.png"
    path.write_bytes(b"image")

    db = SessionLocal()
    try:
        queue_file_deletion(db, path=path, reason="test")
        db.commit()

        import app.services.file_deletion as deletion_service

        monkeypatch.setattr(deletion_service, "_unlink", lambda _: (_ for _ in ()).throw(OSError("busy")))
        deleted, failed = process_file_deletion_jobs(db, data_dir=tmp_path)
        assert (deleted, failed) == (0, 1)
        job = db.query(FileDeletionJobModel).one()
        assert job.status == "failed"
        assert job.attempts == 1
        assert path.exists()

        def succeed(value):
            if value:
                Path(value).unlink(missing_ok=True)

        monkeypatch.setattr(deletion_service, "_unlink", succeed)
        job.next_attempt_at = datetime.now(timezone.utc)
        db.commit()
        deleted, failed = process_file_deletion_jobs(db, data_dir=tmp_path)
        assert (deleted, failed) == (1, 0)
        assert not path.exists()
        assert db.query(FileDeletionJobModel).one().status == "completed"
    finally:
        db.close()
