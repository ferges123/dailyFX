from __future__ import annotations

import os
import sys
from pathlib import Path

LOCKS_DIR = Path("data") / "locks"
AGENT_QUEUE_DIR = Path("data") / "agent-queues"
_RECOVERY_DIR_BUFFER_SECONDS = 300.0
_RECOVERY_FILE_BUFFER_SECONDS = 10.0
_DAEMON_STARTUP_TIMEOUT = 10.0
IS_TESTING = "pytest" in sys.modules or "py.test" in sys.modules


def is_testing() -> bool:
    """Detect test execution even when this module was imported early."""
    return IS_TESTING or bool(os.environ.get("PYTEST_CURRENT_TEST")) or os.environ.get(
        "DAILYFX_AGENT_TESTING"
    ) == "1"

_LIST_SCHEDULES_TIMEOUT = 60
_DOCKER_COMPOSE_CONFIG_TIMEOUT = 30
_DOCKER_COMPOSE_HEALTH_TIMEOUT = 30
_DOCKER_COMPOSE_SCHEDULES_TIMEOUT = 60
_DOCTOR_HTTP_PROBE_TIMEOUT = 10
