from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get("/log", response_class=PlainTextResponse)
def get_debug_log() -> str:
    """Get the latest debug log file content."""
    log_dir = Path("/data/logs")

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
