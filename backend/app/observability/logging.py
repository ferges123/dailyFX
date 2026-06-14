import json
import logging
import sys
from datetime import datetime, timezone

from app.config import get_settings


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        exc_info = record.exc_info
        exception_str = None
        if exc_info:
            exception_str = self.formatException(exc_info)

        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if exception_str:
            log_data["exception"] = exception_str

        return json.dumps(log_data)


def setup_logging():
    settings = get_settings()
    if not settings.log_json:
        return

    root_logger = logging.getLogger()

    # Remove existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Add our StreamHandler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Configure uvicorn loggers to propagate to root logger so they use our formatter
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(logger_name)
        for h in list(uv_logger.handlers):
            uv_logger.removeHandler(h)
        uv_logger.propagate = True
