from __future__ import annotations

import fcntl
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, TextIO

from dailyfx_agent.config import LOCKS_DIR


def _get_locks_dir() -> Path:
    return LOCKS_DIR


def _unlink_if_same_file(stream: TextIO, path: Path) -> None:
    """Unlink only the inode held by ``stream``, never a replacement lock."""
    try:
        stream_stat = os.fstat(stream.fileno())
        path_stat = path.stat()
    except FileNotFoundError:
        return
    if (stream_stat.st_dev, stream_stat.st_ino) == (path_stat.st_dev, path_stat.st_ino):
        path.unlink(missing_ok=True)


@contextmanager
def _locked_file(path: Path) -> Iterator[TextIO]:
    fd = os.open(path, os.O_RDWR)
    stream = None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        stream = os.fdopen(fd, "r+", encoding="utf-8")
        yield stream
    finally:
        if stream is not None:
            stream.close()
        else:
            os.close(fd)



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

    # O_EXCL elects one creator; flock protects readers and stale-file cleanup.
    for _ in range(10):
        try:
            fd = os.open(lock_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            try:
                with _locked_file(lock_file) as stream:
                    try:
                        data = json.load(stream)
                    except (json.JSONDecodeError, ValueError, KeyError):
                        sys.stderr.write(
                            f"warning: removing invalid lock file for schedule {schedule_id}\n"
                        )
                        _unlink_if_same_file(stream, lock_file)
                        continue
                    pid = int(data.get("pid", 0))
                    owner_target = data.get("target", target)
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        sys.stderr.write(
                            f"warning: removing stale lock file for schedule {schedule_id} (PID {pid} was not found)\n"
                        )
                        _unlink_if_same_file(stream, lock_file)
                        continue
                    raise RuntimeError(
                        f"Error: another agent (PID {pid}) is already running schedule {schedule_id} for target {owner_target}."
                    )
            except FileNotFoundError:
                continue
        else:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    fd = -1
                    json.dump(lock_data, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                lock_file.unlink(missing_ok=True)
                raise
            finally:
                if fd >= 0:
                    os.close(fd)
            return

    raise RuntimeError(f"Error: could not acquire lock for schedule {schedule_id}.")


def _update_lock_for_daemon_child(schedule_id: int, target: str, child_pid: int) -> None:
    lock_file = _get_locks_dir() / f"dailyfx-s{schedule_id}.lock"
    try:
        with _locked_file(lock_file) as stream:
            data = json.load(stream)
            data["pid"] = child_pid
            data["child_pid"] = child_pid
            data["owner_role"] = "daemon_child"
            stream.seek(0)
            stream.truncate()
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileNotFoundError:
        return
    except Exception as exc:
        sys.stderr.write(
            f"warning: failed to update lock for daemon child {child_pid}: {exc}\n"
        )


def _release_lock(schedule_id: int, target: str) -> None:
    lock_file = _get_locks_dir() / f"dailyfx-s{schedule_id}.lock"
    try:
        with _locked_file(lock_file) as stream:
            try:
                data = json.load(stream)
                lock_pids = {
                    int(data.get("pid", 0) or 0),
                    int(data.get("child_pid", 0) or 0),
                }
                if os.getpid() in lock_pids:
                    _unlink_if_same_file(stream, lock_file)
            except (json.JSONDecodeError, ValueError, KeyError, OSError):
                _unlink_if_same_file(stream, lock_file)
    except FileNotFoundError:
        return
