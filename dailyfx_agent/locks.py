from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dailyfx_agent.config import LOCKS_DIR
from dailyfx_agent.utils import _get_pkg_attr


def _get_locks_dir() -> Path:
    return _get_pkg_attr("LOCKS_DIR", LOCKS_DIR)


def _get_os():
    return _get_pkg_attr("os", os)


def _acquire_lock(schedule_id: int, target: str) -> None:
    os_mod = _get_os()
    locks_dir = _get_locks_dir()
    locks_dir.mkdir(parents=True, exist_ok=True)
    lock_file = locks_dir / f"dailyfx-s{schedule_id}.lock"

    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            pid = int(data.get("pid", 0))
            owner_target = data.get("target", target)
            try:
                os_mod.kill(pid, 0)
                raise RuntimeError(
                    f"Error: another agent (PID {pid}) is already running schedule {schedule_id} for target {owner_target}."
                )
            except OSError:
                sys.stderr.write(
                    f"warning: removing stale lock file for schedule {schedule_id} (PID {pid} was not found)\n"
                )
                lock_file.unlink(missing_ok=True)
        except (json.JSONDecodeError, ValueError, KeyError, OSError):
            sys.stderr.write(
                f"warning: removing invalid lock file for schedule {schedule_id}\n"
            )
            lock_file.unlink(missing_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    lock_data = {
        "pid": os_mod.getpid(),
        "parent_pid": os_mod.getpid(),
        "child_pid": None,
        "owner_role": "foreground",
        "started_at": started_at,
        "target": target,
    }
    lock_file.write_text(json.dumps(lock_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    except Exception:
        pass


def _release_lock(schedule_id: int, target: str) -> None:
    os_mod = _get_os()
    locks_dir = _get_locks_dir()
    lock_file = locks_dir / f"dailyfx-s{schedule_id}.lock"
    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            lock_pids = {
                int(data.get("pid", 0) or 0),
                int(data.get("child_pid", 0) or 0),
            }
            if os_mod.getpid() in lock_pids:
                lock_file.unlink(missing_ok=True)
        except Exception:
            lock_file.unlink(missing_ok=True)
