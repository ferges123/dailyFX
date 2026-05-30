"""Tests for utility modules."""
import pytest
from datetime import date

from app.utils.date_utils import parse_date
from app.utils.url_utils import normalize_base_url, normalize_api_url
from app.utils.query_params import query_str, query_int, query_float, query_date


class TestDateUtils:
    """Tests for date_utils module."""

    def test_parse_date_valid(self):
        assert parse_date("2024-01-15") == date(2024, 1, 15)
        assert parse_date("2024-12-31") == date(2024, 12, 31)

    def test_parse_date_invalid(self):
        assert parse_date(None) is None
        assert parse_date("") is None
        assert parse_date("  ") is None
        assert parse_date("invalid") is None
        assert parse_date("2024-13-01") is None
        assert parse_date("not-a-date") is None

    def test_parse_date_edge_cases(self):
        assert parse_date(123) is None
        assert parse_date([]) is None
        assert parse_date({}) is None


class TestUrlUtils:
    """Tests for url_utils module."""

    def test_normalize_base_url(self):
        assert normalize_base_url("https://example.com/") == "https://example.com"
        assert normalize_base_url("https://example.com///") == "https://example.com"
        assert normalize_base_url("  https://example.com  ") == "https://example.com"
        assert normalize_base_url("https://example.com/path/") == "https://example.com/path"

    def test_normalize_api_url_with_api(self):
        assert normalize_api_url("https://example.com/api") == "https://example.com/api"
        assert normalize_api_url("https://example.com/api/") == "https://example.com/api"

    def test_normalize_api_url_without_api(self):
        assert normalize_api_url("https://example.com") == "https://example.com/api"
        assert normalize_api_url("https://example.com/") == "https://example.com/api"
        assert normalize_api_url("  https://example.com  ") == "https://example.com/api"


class TestQueryParams:
    """Tests for query_params module."""

    def test_query_str(self):
        assert query_str("hello", "default") == "hello"
        assert query_str("  hello  ", "default") == "  hello  "
        assert query_str("", "default") == "default"
        assert query_str("  ", "default") == "default"
        assert query_str(None, "default") == "default"
        assert query_str(123, "default") == "default"

    def test_query_int(self):
        assert query_int(42, 0) == 42
        assert query_int("42", 0) == 42
        assert query_int("-10", 0) == -10
        assert query_int("invalid", 99) == 99
        assert query_int("", 99) == 99
        assert query_int(None, 99) == 99
        assert query_int([], 99) == 99

    def test_query_float(self):
        assert query_float(3.14, 0.0) == 3.14
        assert query_float("3.14", 0.0) == 3.14
        assert query_float("-2.5", 0.0) == -2.5
        assert query_float(42, 0.0) == 42.0
        assert query_float("invalid", 1.5) == 1.5
        assert query_float("", 1.5) == 1.5
        assert query_float(None, 1.5) == 1.5

    def test_query_date(self):
        assert query_date("2024-01-15") == date(2024, 1, 15)
        assert query_date("2024-12-31") == date(2024, 12, 31)
        assert query_date("invalid") is None
        assert query_date("") is None
        assert query_date("  ") is None
        assert query_date(None) is None
        assert query_date(123) is None


class TestDebugLogger:
    """Tests for debug_logger module."""

    def test_debug_log_disabled(self):
        from app.utils import debug_logger
        from unittest.mock import patch
        debug_logger.set_debug_mode(False)
        with patch("app.utils.debug_logger.logger") as mock_logger:
            debug_logger.debug_log("test message", task_id="task-123", key="val")
            mock_logger.info.assert_not_called()

    def test_debug_log_enabled(self, tmp_path):
        from app.utils import debug_logger
        from unittest.mock import patch
        with patch("app.utils.debug_logger.Path", return_value=tmp_path), \
             patch("app.utils.debug_logger.logger") as mock_logger:
            debug_logger.set_debug_mode(True)
            mock_logger.reset_mock()
            try:
                debug_logger.debug_log("test message", task_id="task-123", key="val")
                mock_logger.info.assert_called_once_with("DEBUG: [task-123] test message | key=val")
            finally:
                debug_logger.set_debug_mode(False)

