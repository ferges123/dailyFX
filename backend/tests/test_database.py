from unittest.mock import MagicMock, patch
import pytest
from app.database import get_db

def test_get_db_rollback_on_exception():
    mock_session = MagicMock()
    
    with patch("app.database.SessionLocal", return_value=mock_session), \
         patch("app.database._ensure_engine"):
        
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
    
    with patch("app.database.SessionLocal", return_value=mock_session), \
         patch("app.database._ensure_engine"):
        
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
