from __future__ import annotations

import sys
from pathlib import Path

LOCKS_DIR = Path("data") / "locks"
_DAEMON_STARTUP_TIMEOUT = 10.0
IS_TESTING = "pytest" in sys.modules or "py.test" in sys.modules
