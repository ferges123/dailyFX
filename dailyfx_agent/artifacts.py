from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path


def _task_stage_label(stage: str) -> str:
    normalized = stage.strip().lower()
    if normalized in {"selecting_asset", "searching_assets", "asset_selection"}:
        return "[search]"
    if normalized in {"running", "running_pipeline", "planning"}:
        return "[plan]"
    if normalized in {"applying_effect", "executing_effect", "rendering"}:
        return "[render]"
    if normalized in {"analyzing_image", "analyzing_final_image", "embedding_metadata"}:
        return "[analyze]"
    if normalized in {"saving_result", "host_render_ready", "host_finalizing"}:
        return "[save]"
    if normalized in {"succeeded", "completed", "done"}:
        return "[done]"
    if normalized in {"failed", "error"}:
        return "[fail]"
    return f"[{normalized[:20] or 'task'}]"


def _cleanup_manifest_files(args: object, *manifest_paths: object) -> None:
    if getattr(args, "keep_manifest", False):
        return
    explicit_path = getattr(args, "manifest_path", None)
    seen: set[Path] = set()
    for candidate in manifest_paths:
        if not isinstance(candidate, Path) or candidate in seen:
            continue
        seen.add(candidate)
        if not explicit_path or candidate.name.startswith("dailyfx-run-"):
            candidate.unlink(missing_ok=True)


def _task_trace_labels(task_trace: object, limit: int = 5) -> list[str]:
    if not isinstance(task_trace, list):
        return []

    labels: list[str] = []
    for entry in task_trace[-limit:]:
        if not isinstance(entry, dict):
            text = str(entry).strip()
            if text:
                labels.append(text)
            continue

        stage = str(entry.get("stage") or entry.get("step") or "task").strip() or "task"
        message = str(entry.get("message") or "").strip()
        progress = entry.get("progress")
        parts = [_task_stage_label(stage)]
        if isinstance(progress, (int, float)):
            parts.append(f"{int(float(progress) * 100)}%")
        if message:
            parts.append(message)
        labels.append(" ".join(parts))

    return labels[-limit:]


def _rotate_target_logs(log_dir: Path, keep: int = 5) -> None:
    if keep <= 0 or not log_dir.exists():
        return

    def get_mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    try:
        logs = sorted(
            (path for path in log_dir.glob("dailyfx-agent-*.log") if path.is_file()),
            key=get_mtime,
        )
        for old_log in logs[:-keep]:
            old_log.unlink(missing_ok=True)
    except OSError:
        pass


def _write_target_log(
    *,
    log_dir: Path,
    task_id: str,
    target: str,
    stdout: str,
    stderr: str,
    returncode: int,
) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    log_path = log_dir / f"dailyfx-agent-{task_id}-{target}-{timestamp}.log"
    log_path.write_text(
        "\n".join(
            [
                f"task_id={task_id}",
                f"target={target}",
                f"returncode={returncode}",
                "",
                "=== stdout ===",
                stdout.rstrip(),
                "",
                "=== stderr ===",
                stderr.rstrip(),
                "",
            ]
        ),
        encoding="utf-8",
    )
    log_path.chmod(0o600)
    _rotate_target_logs(log_dir, keep=5)
    return log_path


def _safe_task_id(task_id: str) -> str:
    original = task_id.strip() or "target"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", original)
    if len(safe) <= 120:
        return safe
    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()[:12]
    return f"{safe[:107]}-{digest}"


def _task_artifact_dir(task_id: str) -> Path:
    return Path("data") / "logs" / "agent" / "tasks" / _safe_task_id(task_id)


def _write_task_text_artifact(task_id: str, name: str, content: str) -> Path | None:
    try:
        artifact_dir = _task_artifact_dir(task_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)
        return path
    except OSError:
        return None


def _write_task_json_artifact(task_id: str, name: str, payload: object) -> Path | None:
    try:
        artifact_dir = _task_artifact_dir(task_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        path.chmod(0o600)
        return path
    except (OSError, TypeError):
        return None


def _copy_task_artifact(task_id: str, source: Path, name: str) -> Path | None:
    try:
        if not source.exists():
            return None
        artifact_dir = _task_artifact_dir(task_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / name
        shutil.copyfile(source, path)
        return path
    except OSError:
        return None
