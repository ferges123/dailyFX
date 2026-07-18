import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.database import get_db, get_db_dependency


def test_get_db_rollback_on_exception():
    mock_session = MagicMock()

    with patch("app.database.SessionLocal", return_value=mock_session), patch("app.database._ensure_engine"):
        db_gen = get_db()
        db = next(db_gen)

        assert db == mock_session

        # Simulate an exception being thrown inside the block using the db session
        with pytest.raises(ValueError, match="test database error"):
            db_gen.throw(ValueError("test database error"))

        # Verify that rollback was called on the session
        mock_session.rollback.assert_called_once()
        # Verify that close was also called
        mock_session.close.assert_called_once()


def test_get_db_no_exception_closes_session():
    mock_session = MagicMock()

    with patch("app.database.SessionLocal", return_value=mock_session), patch("app.database._ensure_engine"):
        db_gen = get_db()
        db = next(db_gen)

        assert db == mock_session

        # Simulate normal generator termination
        try:
            next(db_gen)
        except StopIteration:
            pass

        # Verify that rollback was NOT called, but close was
        mock_session.rollback.assert_not_called()
        mock_session.close.assert_called_once()


def test_get_db_dependency_rolls_back_on_exception():
    mock_session = MagicMock()

    async def exercise():
        with patch("app.database.SessionLocal", return_value=mock_session), patch("app.database._ensure_engine"):
            db_gen = get_db_dependency()
            db = await db_gen.__anext__()
            assert db == mock_session
            with pytest.raises(ValueError, match="async database error"):
                await db_gen.athrow(ValueError("async database error"))

    asyncio.run(exercise())
    mock_session.rollback.assert_called_once()
    mock_session.close.assert_called_once()


def test_init_db_fallback_path_resolution(monkeypatch):
    from pathlib import Path

    upgrade_called = []

    monkeypatch.setattr("alembic.command.upgrade", lambda cfg, revision: upgrade_called.append(cfg))
    monkeypatch.setattr("app.database._ensure_engine", lambda: None)
    monkeypatch.setattr("app.services.generation.bootstrap.bootstrap_builtin_ai_effects", lambda: None)
    monkeypatch.setattr("app.database._initialized_databases", set())

    real_exists = Path.exists

    def mock_exists(self):
        if "alembic.ini" in str(self):
            if str(self) == "/app/alembic.ini":
                return True
            return False
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", mock_exists)

    from app.database import init_db

    init_db()

    assert len(upgrade_called) == 1
    assert upgrade_called[0].config_file_name == "/app/alembic.ini"
