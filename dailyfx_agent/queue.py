from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from dailyfx_agent.config import AGENT_QUEUE_DIR


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


def _read_owner(root: Path) -> dict | None:
    path = root / "owner.json"
    try:
        owner = json.loads(path.read_text(encoding="utf-8"))
        if _pid_alive(int(owner.get("pid", 0))):
            return owner
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    path.unlink(missing_ok=True)
    return None


def enqueue_or_claim(target: str, argv: list[str]) -> tuple[str, bool, int, int | None]:
    """Persist a job and claim the target worker if no live owner exists."""
    job_id = uuid.uuid4().hex
    with _queue_lock(target) as root:
        pending = root / "pending"
        pending.mkdir(exist_ok=True)
        job_path = pending / f"{time.time_ns()}-{job_id}.json"
        tmp_path = job_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps({"job_id": job_id, "argv": argv}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, job_path)

        owner = _read_owner(root)
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


def queue_depth(target: str) -> int:
    root = AGENT_QUEUE_DIR / target / "pending"
    return len(list(root.glob("*.json"))) if root.exists() else 0


def queue_runs(target: str) -> int:
    """Return the number of repeat executions represented by pending jobs."""
    root = AGENT_QUEUE_DIR / target / "pending"
    total = 0
    if not root.exists():
        return 0
    for path in root.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            argv = [str(item) for item in payload.get("argv", [])]
            repeat = 1
            for index, item in enumerate(argv):
                if item in {"--repeat", "-x"} and index + 1 < len(argv):
                    repeat = max(1, int(argv[index + 1]))
                    break
            total += repeat
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            total += 1
    return total
