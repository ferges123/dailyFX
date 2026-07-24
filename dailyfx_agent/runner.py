from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dailyfx_agent.artifacts import (
    _cleanup_manifest_files,
    _copy_task_artifact,
    _rotate_target_logs,
    _safe_task_id,
    _task_artifact_dir,
    _task_stage_label,
    _task_trace_labels,
    _write_target_log,
    _write_task_json_artifact,
    _write_task_text_artifact,
)
from dailyfx_agent.cli import (
    _build_backend_command,
    _build_parser,
    _build_target_command,
    _parse_args,
    _validate_command_templates,
)
from dailyfx_agent.config import _DAEMON_STARTUP_TIMEOUT, _LIST_SCHEDULES_TIMEOUT
from dailyfx_agent.daemon import _handle_status, _handle_stop, _process_start_time
from dailyfx_agent.doctor import _handle_clean_manifests, _handle_doctor
from dailyfx_agent.locks import _acquire_lock, _release_lock, _update_lock_for_daemon_child
from dailyfx_agent.manifest import (
    _augment_host_prompt,
    _load_manifest,
    _normalize_host_manifest,
)
from dailyfx_agent.models import (
    _get_agy_models,
    _get_codex_models,
    _list_agy_models,
    _list_codex_models,
    _print_model_list_header,
)
from dailyfx_agent.queue import (
    claim_job,
    enqueue_or_claim,
    finish_job,
    next_job,
    release_owner,
    update_owner_pid,
    update_running_job_progress,
)
from dailyfx_agent.recovery import (
    _find_latest_agy_image,
    _find_latest_codex_image,
    _validate_output_image,
)
from dailyfx_agent.utils import (
    _atomic_write_text,
    _container_to_host_image_path,
    _print_command,
    _print_manifest,
    _print_note,
    _run_subprocess_with_active_tracking,
    _setup_signal_handlers,
)
from dailyfx_agent.workflow import (
    _handle_command_mode,
    _handle_dry_run,
    _manifest_path_for_run,
    _mark_host_task_failed,
    _recover_target_output,
    _resolve_output_path,
    _resolve_source_image,
    _run_backend_command,
    _run_target_with_spinner,
    _run_workflow_iteration,
    _validate_model,
)

__all__ = [
    "_task_stage_label",
    "_cleanup_manifest_files",
    "_task_trace_labels",
    "_rotate_target_logs",
    "_write_target_log",
    "_safe_task_id",
    "_task_artifact_dir",
    "_write_task_text_artifact",
    "_write_task_json_artifact",
    "_copy_task_artifact",
    "_recover_target_output",
    "_mark_host_task_failed",
    "_run_target_with_spinner",
    "_handle_command_mode",
    "_validate_model",
    "_manifest_path_for_run",
    "_run_backend_command",
    "_resolve_source_image",
    "_resolve_output_path",
    "_handle_dry_run",
    "_run_workflow_iteration",
    "_drain_queue",
    "_daemon_child_main_impl",
    "_daemon_child_main",
    "main",
]


def _drain_queue(queue_target: str, main_fn=None) -> None:
    if main_fn is None:
        main_fn = main
    try:
        while True:
            pending = next_job(queue_target)
            if pending is None:
                break
            payload, running_path = pending
            try:
                if not isinstance(payload, dict):
                    raise ValueError("queue payload must be an object")
                raw_argv = payload.get("argv", [])
                if not isinstance(raw_argv, list):
                    raise ValueError("queue payload argv must be a list")
                job_argv = [
                    str(item) for item in raw_argv
                    if item not in {"--daemon", "-d", "--_queue-worker"}
                ]
                main_fn(job_argv + ["--_queue-worker"])
            except Exception as exc:
                sys.stderr.write(f"Error processing queued job {running_path.name}: {exc}\n")
            finally:
                finish_job(running_path)
    finally:
        release_owner(queue_target, os.getpid())


def _daemon_child_main_impl(
    args: argparse.Namespace,
    backend_command: list[str],
    project_dir_str: str,
    manifest_path_str: str,
    shared_manifest_path_str: str,
    queue_target: str | None,
    queue_owner: bool,
    queue_job_id: str | None,
    repeat: int,
    status_data: dict[str, object],
    ready_event: multiprocessing.Event,
    pid_file_str: str,
    log_file_path_str: str,
) -> None:
    project_dir = Path(project_dir_str)
    manifest_path = Path(manifest_path_str)
    shared_manifest_path = Path(shared_manifest_path_str)
    pid_file = Path(pid_file_str)
    log_file_path = Path(log_file_path_str)

    status_data = dict(status_data)

    try:
        os.umask(0o077)
        metadata_file = pid_file.with_name(pid_file.name + ".json")
        metadata = {
            "pid": os.getpid(), "process_start_time": _process_start_time(os.getpid()),
            "schedule_id": args.schedule_id,
            "target": args.target, "started_at": datetime.now(timezone.utc).isoformat(),
            "log_path": str(log_file_path.resolve()),
            "manifest_path": str(manifest_path.resolve()), "repeat": repeat,
        }
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(pid_file, f"{os.getpid()}\n")
        _atomic_write_text(metadata_file, json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    except BaseException:
        pid_file.unlink(missing_ok=True)
        pid_file.with_name(pid_file.name + ".json").unlink(missing_ok=True)
        _cleanup_manifest_files(args, manifest_path, shared_manifest_path)
        return

    try:
        sys.stdout.flush()
        sys.stderr.flush()
        log_fd = os.open(str(log_file_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.fchmod(log_fd, 0o600)
        devnull = os.open(os.devnull, os.O_RDONLY)
        try:
            os.dup2(devnull, 0)
            os.dup2(log_fd, 1)
            os.dup2(log_fd, 2)
        finally:
            os.close(devnull)
            os.close(log_fd)
    except OSError as exc:
        sys.stderr.write(f"Error: daemon log redirection failed: {exc}\n")
        pid_file.unlink(missing_ok=True)
        pid_file.with_name(pid_file.name + ".json").unlink(missing_ok=True)
        _cleanup_manifest_files(args, manifest_path, shared_manifest_path)
        return

    ready_event.set()

    for run_index in range(1, repeat + 1):
        if repeat > 1:
            print(f"--- run {run_index}/{repeat} ---")

        manifest_path = _manifest_path_for_run(args, run_index, manifest_path if run_index == 1 else None)
        shared_manifest_path = manifest_path

        _run_workflow_iteration(
            args, backend_command, project_dir,
            manifest_path, shared_manifest_path, status_data,
        )
        if queue_target and queue_job_id:
            update_running_job_progress(queue_target, queue_job_id, run_index)

    if queue_owner and queue_target and queue_job_id:
        running_dir = Path("data") / "agent-queues" / queue_target / "running"
        for path in running_dir.glob(f"*-{queue_job_id}.json"):
            finish_job(path)

    if queue_owner and queue_target:
        _drain_queue(queue_target)

    _cleanup_manifest_files(args, manifest_path, shared_manifest_path)
    pid_file.unlink(missing_ok=True)
    pid_file.with_name(pid_file.name + ".json").unlink(missing_ok=True)
    if status_data.get("task_id"):
        _write_task_json_artifact(str(status_data["task_id"]), "status.json", status_data)
    if getattr(args, "json_status", False):
        print(json.dumps(status_data, ensure_ascii=False, indent=2))


def _daemon_child_main(*args, **kwargs) -> None:
    daemon_args = args[0] if args else kwargs["args"]
    try:
        _daemon_child_main_impl(*args, **kwargs)
    finally:
        if daemon_args.schedule_id is not None:
            _release_lock(daemon_args.schedule_id, daemon_args.target)


def main(argv: list[str] | None = None) -> int:
    _setup_signal_handlers()
    status_data = {
        "task_id": "", "schedule_id": None, "target": None, "model": None,
        "stage": "prepare", "manifest_path": None, "source_image_path": None,
        "output_path": None, "target_log_path": None, "recovery_attempted": False,
        "recovered_from": None, "artifact_dir": None, "output_image": None, "error": None,
    }

    effective_argv = sys.argv[1:] if argv is None else argv
    if len(effective_argv) == 0:
        _build_parser().print_help()
        return 0

    args = _parse_args(effective_argv)
    status_data["schedule_id"] = args.schedule_id
    status_data["target"] = args.target
    status_data["model"] = args.model
    _validate_command_templates(args)

    model_exit = _validate_model(args)
    if model_exit is not None:
        return model_exit

    project_dir = Path(args.project_dir)
    manifest_path = Path(args.manifest_path) if args.manifest_path else Path("data") / f"dailyfx-run-{uuid.uuid4().hex[:8]}.json"
    shared_manifest_path = manifest_path
    backend_command = _build_backend_command(args)

    command_exit = _handle_command_mode(args)
    if command_exit is not None:
        return command_exit

    if args.schedule_id is None or args.target is None:
        sys.stderr.write("schedule-id and target are required unless --list-schedules is used\n")
        return 1

    queue_target = args.target if args.target in {"agy", "codex"} else None
    queue_owner = False
    queue_job_id = None
    if queue_target and not args._queue_worker and not args.dry_run:
        queue_job_id, queue_owner, position, owner_pid = enqueue_or_claim(queue_target, list(effective_argv))
        if not queue_owner:
            print(f"queued: target={queue_target} job={queue_job_id} position={position} worker_pid={owner_pid}")
            return 0
        claim_job(queue_target, queue_job_id)

    if args.dry_run:
        return _handle_dry_run(args, manifest_path, shared_manifest_path)

    repeat = max(1, args.repeat)
    last_exit = 0
    pid_file = None
    lock_released = False

    if args.schedule_id is not None:
        try:
            _acquire_lock(args.schedule_id, args.target)
        except RuntimeError as exc:
            if queue_owner and queue_target and queue_job_id:
                running_dir = Path("data") / "agent-queues" / queue_target / "running"
                for path in running_dir.glob(f"*-{queue_job_id}.json"):
                    finish_job(path)
                release_owner(queue_target, os.getpid())
            sys.stderr.write(f"{exc}\n")
            return 1

    if args.daemon:
        if args.pid_file:
            pid_file = Path(args.pid_file)
        else:
            target_str = args.target if args.target else "default"
            pid_file = Path("data") / f"dailyfx-agent-{target_str}.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        log_file_path = Path("data") / "logs" / "agent" / f"{pid_file.stem}.log"
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        spawn_ctx = multiprocessing.get_context('spawn')
        ready_event = spawn_ctx.Event()

        proc = spawn_ctx.Process(
            target=_daemon_child_main,
            args=(
                args, backend_command, str(project_dir),
                str(manifest_path), str(shared_manifest_path),
                queue_target, queue_owner, queue_job_id,
                repeat, status_data, ready_event,
                str(pid_file), str(log_file_path),
            ),
        )
        try:
            proc.start()
        except BaseException:
            _cleanup_manifest_files(args, manifest_path, shared_manifest_path)
            if queue_owner and queue_target and queue_job_id:
                running_dir = Path("data") / "agent-queues" / queue_target / "running"
                for path in running_dir.glob(f"*-{queue_job_id}.json"):
                    finish_job(path)
                release_owner(queue_target, os.getpid())
            if args.schedule_id is not None:
                _release_lock(args.schedule_id, args.target)
                lock_released = True
            raise

        if not ready_event.wait(timeout=_DAEMON_STARTUP_TIMEOUT):
            proc.terminate()
            proc.join(timeout=5)
            _cleanup_manifest_files(args, manifest_path, shared_manifest_path)
            if queue_owner and queue_target and queue_job_id:
                running_dir = Path("data") / "agent-queues" / queue_target / "running"
                for path in running_dir.glob(f"*-{queue_job_id}.json"):
                    finish_job(path)
                release_owner(queue_target, os.getpid())
            if args.schedule_id is not None:
                _release_lock(args.schedule_id, args.target)
                lock_released = True
            pid_file.unlink(missing_ok=True)
            pid_file.with_name(pid_file.name + ".json").unlink(missing_ok=True)
            sys.stderr.write("Error: daemon failed to start\n")
            return 1

        lock_released = True
        if args.schedule_id is not None:
            _update_lock_for_daemon_child(args.schedule_id, args.target, proc.pid)
        if queue_owner and queue_target:
            update_owner_pid(queue_target, proc.pid)

        print(f"daemon started: pid={proc.pid} pidfile={pid_file}")
        return 0

    try:
        for run_index in range(1, repeat + 1):
            if repeat > 1:
                print(f"--- run {run_index}/{repeat} ---")

            manifest_path = _manifest_path_for_run(args, run_index, manifest_path if run_index == 1 else None)
            shared_manifest_path = manifest_path

            run_exit = _run_workflow_iteration(
                args, backend_command, project_dir,
                manifest_path, shared_manifest_path, status_data,
            )
            if queue_target and queue_job_id:
                update_running_job_progress(queue_target, queue_job_id, run_index)
            if run_exit != 0:
                last_exit = run_exit
    finally:
        _cleanup_manifest_files(args, manifest_path, shared_manifest_path)
        if queue_owner and queue_target and queue_job_id:
            running_dir = Path("data") / "agent-queues" / queue_target / "running"
            for path in running_dir.glob(f"*-{queue_job_id}.json"):
                finish_job(path)
        if args.schedule_id is not None:
            if not lock_released:
                _release_lock(args.schedule_id, args.target)
        if status_data.get("task_id"):
            _write_task_json_artifact(str(status_data["task_id"]), "status.json", status_data)
        if getattr(args, "json_status", False):
            print(json.dumps(status_data, ensure_ascii=False, indent=2))

    if queue_owner and queue_target:
        _drain_queue(queue_target)

    return last_exit
