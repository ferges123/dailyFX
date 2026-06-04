"""Debug logging utility for detailed troubleshooting."""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_debug_enabled = False
_debug_file = None

_MAX_LOG_FILES = 10
_MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB


def _rotate_logs(log_dir: Path) -> None:
    logs = sorted(log_dir.glob("debug_*.log"), key=lambda p: p.stat().st_mtime)
    while len(logs) >= _MAX_LOG_FILES:
        logs.pop(0).unlink(missing_ok=True)


def set_debug_mode(enabled: bool):
    """Enable or disable debug mode."""
    global _debug_enabled, _debug_file
    _debug_enabled = enabled

    if enabled:
        if _debug_file is None:
            try:
                log_dir = Path("/data/logs")
                log_dir.mkdir(parents=True, exist_ok=True)
                _rotate_logs(log_dir)
                log_file = log_dir / f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                _debug_file = open(log_file, "a", encoding="utf-8")
                debug_log(f"Debug mode enabled - logging to {log_file}")
            except Exception as e:
                logger.warning(f"Failed to open debug log file: {e}")
                _debug_enabled = False
    else:
        if _debug_file is not None:
            try:
                _debug_file.close()
            except Exception:
                pass
            _debug_file = None


def debug_log(message: str, **kwargs):
    """Log debug message if debug mode is enabled."""
    if not _debug_enabled:
        return

    task_id = kwargs.pop("task_id", None)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    if task_id:
        log_line = f"[{timestamp}][{task_id}] {message}"
    else:
        log_line = f"[{timestamp}] {message}"

    if kwargs:
        log_line += " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items())

    if _debug_file:
        try:
            # Rotate if file exceeds max size
            if _debug_file.tell() > _MAX_LOG_SIZE:
                _debug_file.close()
                _rotate_logs(Path("/data/logs"))
                new_file = Path("/data/logs") / f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                globals()["_debug_file"] = open(new_file, "a", encoding="utf-8")
            _debug_file.write(log_line + "\n")
            _debug_file.flush()
        except Exception:
            pass

    # Build and write enriched message to standard logs
    std_message = message
    if task_id:
        std_message = f"[{task_id}] {std_message}"
    if kwargs:
        std_message += " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items())

    logger.info(f"DEBUG: {std_message}")
