from __future__ import annotations

import sys
from pathlib import Path

LOCKS_DIR = Path("data") / "locks"
AGENT_QUEUE_DIR = Path("data") / "agent-queues"
_DAEMON_STARTUP_TIMEOUT = 10.0
IS_TESTING = "pytest" in sys.modules or "py.test" in sys.modules

_LIST_SCHEDULES_TIMEOUT = 60
_DOCKER_COMPOSE_CONFIG_TIMEOUT = 30
_DOCKER_COMPOSE_HEALTH_TIMEOUT = 30
_DOCKER_COMPOSE_SCHEDULES_TIMEOUT = 60
_DOCTOR_HTTP_PROBE_TIMEOUT = 10
