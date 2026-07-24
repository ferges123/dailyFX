from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from dailyfx_agent.config import AGENT_QUEUE_DIR


_OWNER_MAX_AGE_SECONDS = 24 * 60 * 60


@contextmanager
def _queue_lock(target: str):
    import fcntl

    root = AGENT_QUEUE_DIR / target
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".queue.lock"
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield root
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _pid_is_dailyfx_agent(pid: int) -> bool:
    """Reject a reused PID when Linux exposes the process command line."""
    if pid == os.getpid():
        return True
    cmdline_path = Path(f"/proc/{pid}/cmdline")
    if not cmdline_path.exists():
        return True
    try:
        command = cmdline_path.read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return False
    if "dailyfx-agent" in command or "dailyfx_agent" in command:
        return True
    if "python" in command or "multiprocessing" in command:
        try:
            proc_cwd = Path(f"/proc/{pid}/cwd").resolve()
            project_root = Path(__file__).resolve().parent.parent
            if proc_cwd == Path.cwd().resolve() or proc_cwd == project_root:
                return True
        except (OSError, RuntimeError):
            pass
    return False


def _read_owner(root: Path) -> dict | None:
    path = root / "owner.json"
    try:
        owner = json.loads(path.read_text(encoding="utf-8"))
        pid = int(owner.get("pid", 0))
        started_at = float(owner.get("started_at", 0))
        is_recent = time.time() - started_at <= _OWNER_MAX_AGE_SECONDS
        if is_recent and _pid_alive(pid) and _pid_is_dailyfx_agent(pid):
            return owner
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    path.unlink(missing_ok=True)
    return None


def _recover_running(root: Path) -> None:
    """Requeue jobs only after _read_owner() found no valid live owner.

    The caller holds the target queue lock, so a live owner cannot claim or
    mutate a running job concurrently with this recovery pass.
    """
    running = root / "running"
    pending = root / "pending"
    if not running.exists():
        return
    pending.mkdir(exist_ok=True)
    for path in sorted(running.glob("*.json")):
        os.replace(path, pending / path.name)


def _schedule_id_from_argv(argv: list[object]) -> int | None:
    for index, item in enumerate(argv):
        if item in {"--schedule-id", "-s"} and index + 1 < len(argv):
            try:
                return int(argv[index + 1])
            except (TypeError, ValueError):
                return None
    return None


def _repeat_from_argv(argv: list[object]) -> int:
    str_argv = [str(item) for item in argv]
    for index, item in enumerate(str_argv):
        if item in {"--repeat", "-x"} and index + 1 < len(str_argv):
            try:
                return max(1, int(str_argv[index + 1]))
            except (TypeError, ValueError):
                pass
    return 1


def _set_repeat_in_argv(argv: list[object], new_repeat: int) -> list[str]:
    str_argv = [str(item) for item in argv]
    found = False
    new_argv = []
    index = 0
    while index < len(str_argv):
        item = str_argv[index]
        if item in {"--repeat", "-x"} and index + 1 < len(str_argv):
            new_argv.extend([item, str(new_repeat)])
            index += 2
            found = True
        else:
            new_argv.append(item)
            index += 1
    if not found:
        new_argv.extend(["-x", str(new_repeat)])
    return new_argv


def _deduplicate_pending(root: Path) -> None:
    """Keep the oldest pending job for each schedule to prevent retry storms."""
    pending = root / "pending"
    seen: set[int] = set()
    for path in sorted(pending.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            argv = payload.get("argv", [])
            schedule_id = _schedule_id_from_argv(argv) if isinstance(argv, list) else None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if schedule_id is not None:
            if schedule_id in seen:
                path.unlink(missing_ok=True)
            else:
                seen.add(schedule_id)


def enqueue_or_claim(target: str, argv: list[str]) -> tuple[str, bool, int, int | None]:
    """Persist a job and claim the target worker if no live owner exists."""
    with _queue_lock(target) as root:
        pending = root / "pending"
        pending.mkdir(exist_ok=True)
        owner = _read_owner(root)
        if not owner:
            _recover_running(root)
        _deduplicate_pending(root)

        requested_schedule_id = _schedule_id_from_argv(argv)
        if requested_schedule_id is not None:
            for existing in sorted(pending.glob("*.json")):
                try:
                    payload = json.loads(existing.read_text(encoding="utf-8"))
                    existing_argv = payload.get("argv", [])
                    if (
                        not isinstance(existing_argv, list)
                        or _schedule_id_from_argv(existing_argv) != requested_schedule_id
                    ):
                        continue
                    existing_job_id = str(
                        payload.get("job_id") or existing.stem.rsplit("-", 1)[-1]
                    )
                    existing_repeat = _repeat_from_argv(existing_argv)
                    new_repeat = _repeat_from_argv(argv)
                    updated_repeat = existing_repeat + new_repeat
                    payload["argv"] = _set_repeat_in_argv(existing_argv, updated_repeat)

                    tmp_existing = existing.with_suffix(".tmp")
                    tmp_existing.write_text(
                        json.dumps(payload, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
                    os.chmod(tmp_existing, 0o600)
                    os.replace(tmp_existing, existing)

                    if owner:
                        return (
                            existing_job_id,
                            False,
                            len(list(pending.glob("*.json"))),
                            int(owner["pid"]),
                        )
                    owner = {
                        "pid": os.getpid(), "target": target,
                        "job_id": existing_job_id, "started_at": time.time(),
                    }
                    owner_path = root / "owner.json"
                    owner_path.write_text(json.dumps(owner, indent=2) + "\n", encoding="utf-8")
                    os.chmod(owner_path, 0o600)
                    return existing_job_id, True, 1, os.getpid()
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue

        job_id = uuid.uuid4().hex
        job_path = pending / f"{time.time_ns()}-{job_id}.json"
        tmp_path = job_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps({"job_id": job_id, "argv": argv}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, job_path)

        if owner:
            position = len(list(pending.glob("*.json")))
            return job_id, False, position, int(owner["pid"])

        owner = {"pid": os.getpid(), "target": target, "job_id": job_id, "started_at": time.time()}
        owner_path = root / "owner.json"
        owner_path.write_text(json.dumps(owner, indent=2) + "\n", encoding="utf-8")
        os.chmod(owner_path, 0o600)
        return job_id, True, 1, os.getpid()


def claim_job(target: str, job_id: str) -> bool:
    with _queue_lock(target) as root:
        source = next(root.joinpath("pending").glob(f"*-{job_id}.json"), None)
        if source is None:
            return False
        running = root / "running"
        running.mkdir(exist_ok=True)
        os.replace(source, running / source.name)
        return True


def next_job(target: str) -> tuple[dict, Path] | None:
    with _queue_lock(target) as root:
        pending = root / "pending"
        running = root / "running"
        running.mkdir(exist_ok=True)
        for source in sorted(pending.glob("*.json")):
            destination = running / source.name
            os.replace(source, destination)
            try:
                return json.loads(destination.read_text(encoding="utf-8")), destination
            except (OSError, ValueError, json.JSONDecodeError):
                destination.unlink(missing_ok=True)
        return None


def finish_job(path: Path) -> None:
    path.unlink(missing_ok=True)


def release_owner(target: str, pid: int | None = None) -> None:
    with _queue_lock(target) as root:
        owner_path = root / "owner.json"
        try:
            owner = json.loads(owner_path.read_text(encoding="utf-8"))
            if pid is None or int(owner.get("pid", 0)) == pid:
                owner_path.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            owner_path.unlink(missing_ok=True)


def update_owner_pid(target: str, pid: int) -> None:
    with _queue_lock(target) as root:
        owner_path = root / "owner.json"
        try:
            owner = json.loads(owner_path.read_text(encoding="utf-8"))
            owner["pid"] = pid
            owner_path.write_text(json.dumps(owner, indent=2) + "\n", encoding="utf-8")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return


def update_running_job_progress(target: str, job_id: str, completed_runs: int) -> None:
    with _queue_lock(target) as root:
        running = root / "running"
        if not running.exists():
            return
        for path in running.glob(f"*-{job_id}.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["completed_runs"] = completed_runs
                path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
            except (OSError, ValueError, json.JSONDecodeError):
                pass


def queue_depth(target: str) -> int:
    with _queue_lock(target) as root:
        pending = root / "pending"
        return len(list(pending.glob("*.json"))) if pending.exists() else 0


def queue_runs(target: str) -> int:
    """Return the number of repeat executions represented by pending and running jobs."""
    with _queue_lock(target) as root:
        pending = root / "pending"
        running = root / "running"
        total = 0
        if pending.exists():
            for path in pending.glob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    argv = payload.get("argv", [])
                    total += _repeat_from_argv(argv if isinstance(argv, list) else [])
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    total += 1
        if running.exists():
            for path in running.glob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    argv = payload.get("argv", [])
                    total_repeat = _repeat_from_argv(argv if isinstance(argv, list) else [])
                    completed = int(payload.get("completed_runs", 0))
                    remaining = max(0, total_repeat - completed)
                    total += remaining
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    pass
        return total
