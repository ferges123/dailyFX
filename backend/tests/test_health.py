import os
import time
from unittest.mock import MagicMock, patch

import pytest

from app.api.routes_health import health
from app.main import app
from app.version import APP_VERSION


def test_health_and_fastapi_metadata_use_shared_app_version():
    assert health()["version"] == APP_VERSION
    assert app.version == APP_VERSION


def mock_sys_exit(code=0):
    raise SystemExit(code)


def test_healthcheck_script_success(tmp_path):
    from healthcheck import check_health

    # Mock settings
    mock_settings = MagicMock()
    mock_settings.app_port = 8438
    mock_settings.data_dir = tmp_path

    # Create dummy scheduler.health file
    health_file = tmp_path / "scheduler.health"
    health_file.write_text("ok")

    # Mock urllib.request.urlopen and get_settings
    with (
        patch("healthcheck.get_settings", return_value=mock_settings),
        patch("urllib.request.urlopen") as mock_urlopen,
        patch("sys.exit", side_effect=mock_sys_exit),
    ):
        # Mock API response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with pytest.raises(SystemExit) as excinfo:
            check_health()

        assert excinfo.value.code == 0


def test_healthcheck_script_stale_scheduler(tmp_path):
    from healthcheck import check_health

    # Mock settings
    mock_settings = MagicMock()
    mock_settings.app_port = 8438
    mock_settings.data_dir = tmp_path

    # Create stale scheduler.health file (older than 120s)
    health_file = tmp_path / "scheduler.health"
    health_file.write_text("ok")
    stale_time = time.time() - 200
    os.utime(health_file, (stale_time, stale_time))

    with (
        patch("healthcheck.get_settings", return_value=mock_settings),
        patch("urllib.request.urlopen") as mock_urlopen,
        patch("sys.exit", side_effect=mock_sys_exit),
    ):
        # Mock API response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with pytest.raises(SystemExit) as excinfo:
            check_health()

        assert excinfo.value.code == 1


def test_healthcheck_script_api_failure(tmp_path):
    from healthcheck import check_health

    # Mock settings
    mock_settings = MagicMock()
    mock_settings.app_port = 8438
    mock_settings.data_dir = tmp_path

    # Create dummy scheduler.health file
    health_file = tmp_path / "scheduler.health"
    health_file.write_text("ok")

    with (
        patch("healthcheck.get_settings", return_value=mock_settings),
        patch("urllib.request.urlopen") as mock_urlopen,
        patch("sys.exit", side_effect=mock_sys_exit),
    ):
        # Mock API response failing
        mock_urlopen.side_effect = Exception("Connection refused")

        with pytest.raises(SystemExit) as excinfo:
            check_health()

        assert excinfo.value.code == 1
