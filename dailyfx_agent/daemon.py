from __future__ import annotations

import argparse
import json
import os
import signal
import time
from pathlib import Path

from dailyfx_agent.config import AGENT_QUEUE_DIR
from dailyfx_agent.queue import queue_runs


def _get_pid_file_path(args: argparse.Namespace) -> Path:
    if args.pid_file:
        return Path(args.pid_file)
    target_str = args.target if args.target else "default"
    return Path("data") / f"dailyfx-agent-{target_str}.pid"


def _show_single_status(pid_file: Path) -> int:
    if not pid_file.exists():
        print("status: stopped (no PID file)")
        print("note: PID status covers only the host daemon; backend task status is separate")
        return 0

    try:
        pid_str = pid_file.read_text(encoding="utf-8").strip()
        pid = int(pid_str)
    except (ValueError, OSError):
        print("status: stopped (invalid PID file)")
        return 0

    alive = False
    try:
        os.kill(pid, 0)
        alive = True
    except OSError:
        pass

    metadata_file = pid_file.with_name(pid_file.name + ".json")
    metadata = {}
    if metadata_file.exists():
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    if alive:
        print("status: running")
    else:
        print("status: stopped (stale PID file)")

    print(f"pid: {pid}")
    if "schedule_id" in metadata:
        print(f"schedule_id: {metadata['schedule_id']}")
    if "target" in metadata:
        print(f"target: {metadata['target']}")
    if "started_at" in metadata:
        print(f"started_at: {metadata['started_at']}")
    if "log_path" in metadata:
        print(f"log_path: {metadata['log_path']}")
    if "manifest_path" in metadata:
        print(f"manifest_path: {metadata['manifest_path']}")
    if "repeat" in metadata:
        print(f"repeat: {metadata['repeat']}")
    target = str(metadata.get("target") or "")
    if target in {"agy", "codex"}:
        pending_dir = AGENT_QUEUE_DIR / target / "pending"
        print(f"queue_depth: {len(list(pending_dir.glob('*.json'))) if pending_dir.exists() else 0}")
        print(f"queued_runs: {queue_runs(target)}")

    return 0


def _handle_status(args: argparse.Namespace) -> int:
    is_specific = (
        args.pid_file is not None
        or args.schedule_id is not None
        or args.target is not None
    )

    if is_specific:
        return _show_single_status(_get_pid_file_path(args))

    data_dir = Path("data")
    if not data_dir.is_dir():
        print("status: stopped (no PID file)")
        print("note: PID status covers only the host daemon; backend task status is separate")
        return 0

    pid_files = [
        f for f in data_dir.glob("dailyfx-agent-*.pid")
        if f.name.endswith(".pid")
    ]

    if not pid_files:
        print("status: stopped (no PID file)")
        print("note: PID status covers only the host daemon; backend task status is separate")
        return 0

    pid_files.sort()
    for idx, pf in enumerate(pid_files):
        if idx > 0:
            print()
        print(f"[{pf.name}]")
        _show_single_status(pf)

    return 0


def _stop_single_daemon(pid_file: Path) -> int:
    if not pid_file.exists():
        print("status: stopped (no PID file)")
        return 0

    try:
        pid_str = pid_file.read_text(encoding="utf-8").strip()
        pid = int(pid_str)
    except (ValueError, OSError):
        print("status: stopped (invalid PID file)")
        return 0

    killed = False
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)
            except OSError:
                killed = True
                break
        if not killed:
            os.kill(pid, signal.SIGKILL)
            killed = True
    except OSError:
        killed = True

    pid_file.unlink(missing_ok=True)
    metadata_file = pid_file.with_name(pid_file.name + ".json")
    metadata_file.unlink(missing_ok=True)

    print(f"daemon stopped: pid={pid}")
    return 0


def _handle_stop(args: argparse.Namespace) -> int:
    is_specific = (
        args.pid_file is not None
        or args.schedule_id is not None
        or args.target is not None
    )

    if is_specific:
        return _stop_single_daemon(_get_pid_file_path(args))

    data_dir = Path("data")
    if not data_dir.is_dir():
        print("status: stopped (no PID file)")
        return 0

    pid_files = [
        f for f in data_dir.glob("dailyfx-agent-*.pid")
        if f.name.endswith(".pid")
    ]

    if not pid_files:
        print("status: stopped (no PID file)")
        return 0

    pid_files.sort()
    for pf in pid_files:
        print(f"Stopping daemon: {pf.name}")
        _stop_single_daemon(pf)

    return 0
