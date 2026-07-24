from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dailyfx_agent.config import LOCKS_DIR


def _get_locks_dir() -> Path:
    return LOCKS_DIR


def _acquire_lock(schedule_id: int, target: str) -> None:
    locks_dir = _get_locks_dir()
    locks_dir.mkdir(parents=True, exist_ok=True)
    lock_file = locks_dir / f"dailyfx-s{schedule_id}.lock"

    lock_data = {
        "pid": os.getpid(),
        "parent_pid": os.getpid(),
        "child_pid": None,
        "owner_role": "foreground",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "target": target,
    }

    # Creation must be exclusive.  A separate exists()/write_text() pair
    # allows two foreground processes to pass the check and both start.
    for _ in range(3):
        try:
            fd = os.open(lock_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            try:
                data = json.loads(lock_file.read_text(encoding="utf-8"))
                pid = int(data.get("pid", 0))
                owner_target = data.get("target", target)
                try:
                    os.kill(pid, 0)
                except OSError:
                    sys.stderr.write(
                        f"warning: removing stale lock file for schedule {schedule_id} (PID {pid} was not found)\n"
                    )
                    lock_file.unlink(missing_ok=True)
                    continue
                raise RuntimeError(
                    f"Error: another agent (PID {pid}) is already running schedule {schedule_id} for target {owner_target}."
                )
            except (json.JSONDecodeError, ValueError, KeyError, OSError):
                sys.stderr.write(
                    f"warning: removing invalid lock file for schedule {schedule_id}\n"
                )
                lock_file.unlink(missing_ok=True)
                continue
        else:
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(lock_data, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                lock_file.unlink(missing_ok=True)
                raise
            return

    raise RuntimeError(f"Error: could not acquire lock for schedule {schedule_id}.")


def _update_lock_for_daemon_child(schedule_id: int, target: str, child_pid: int) -> None:
    locks_dir = _get_locks_dir()
    lock_file = locks_dir / f"dailyfx-s{schedule_id}.lock"
    if not lock_file.exists():
        return
    try:
        data = json.loads(lock_file.read_text(encoding="utf-8"))
        data["pid"] = child_pid
        data["child_pid"] = child_pid
        data["owner_role"] = "daemon_child"
        lock_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        sys.stderr.write(
            f"warning: failed to update lock for daemon child {child_pid}: {exc}\n"
        )


def _release_lock(schedule_id: int, target: str) -> None:
    locks_dir = _get_locks_dir()
    lock_file = locks_dir / f"dailyfx-s{schedule_id}.lock"
    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            lock_pids = {
                int(data.get("pid", 0) or 0),
                int(data.get("child_pid", 0) or 0),
            }
            if os.getpid() in lock_pids:
                lock_file.unlink(missing_ok=True)
        except Exception:
            lock_file.unlink(missing_ok=True)
