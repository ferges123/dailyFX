from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from app.security import require_auth

router = APIRouter(prefix="/api/debug", tags=["debug"])
DEBUG_LOG_DIR = Path("/data/logs")


@router.get("/log", response_class=PlainTextResponse)
def get_debug_log(_: None = Depends(require_auth)) -> str:
    """Get the latest debug log file content."""
    log_dir = DEBUG_LOG_DIR

    if not log_dir.exists():
        raise HTTPException(status_code=404, detail="No debug logs found")

    log_files = sorted(log_dir.glob("debug_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not log_files:
        raise HTTPException(status_code=404, detail="No debug logs found")

    latest_log = log_files[0]

    try:
        return latest_log.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read log: {exc}") from exc
