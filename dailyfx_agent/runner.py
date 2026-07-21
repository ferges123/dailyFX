from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dailyfx_agent.cli import (
    _build_backend_command,
    _build_parser,
    _build_target_command,
    _parse_args,
    _target_prefix,
    _validate_command_templates,
)
from dailyfx_agent.config import _DAEMON_STARTUP_TIMEOUT, _LIST_SCHEDULES_TIMEOUT
from dailyfx_agent.daemon import _handle_status, _handle_stop
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
from dailyfx_agent.recovery import (
    _find_latest_agy_image,
    _find_latest_codex_image,
    _validate_output_image,
)
from dailyfx_agent.utils import (
    _atomic_write_text,
    _container_to_host_image_path,
    _get_pkg_attr,
    _print_command,
    _print_manifest,
    _print_note,
    _run_subprocess_with_active_tracking,
)


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
    return f"[{normalized[:5] or 'task'}]"


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
    _rotate_target_logs(log_dir, keep=5)
    return log_path


def _safe_task_id(task_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", task_id.strip() or "target")[:120]


def _task_artifact_dir(task_id: str) -> Path:
    return Path("data") / "logs" / "agent" / "tasks" / _safe_task_id(task_id)


def _write_task_text_artifact(task_id: str, name: str, content: str) -> Path | None:
    try:
        artifact_dir = _task_artifact_dir(task_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / name
        path.write_text(content, encoding="utf-8")
        return path
    except OSError:
        return None


def _write_task_json_artifact(task_id: str, name: str, payload: object) -> Path | None:
    try:
        artifact_dir = _task_artifact_dir(task_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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


def _run_target_with_spinner(
    command: list[str],
    *,
    prompt: str,
    task_id: str,
    labels: list[str],
    timeout: int | None = None,
    daemon_mode: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    log_dir = Path("data") / "logs" / "agent"
    fn_write_log = _get_pkg_attr("_write_target_log", _write_target_log)
    if daemon_mode:
        result = _run_subprocess_with_active_tracking(command, prompt, timeout)

        log_path = fn_write_log(
            log_dir=log_dir,
            task_id=task_id or "target",
            target=command[0] if command else "target",
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            returncode=result.returncode,
        )
        return result, log_path

    spinner_labels = (labels[:5] if labels else []) or ["waiting for image provider"]
    spinner_frames = itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
    stop_event = threading.Event()
    spinner_state = {"index": 0}

    def _spinner() -> None:
        while not stop_event.is_set():
            frame = next(spinner_frames)
            label_index = (
                spinner_state["index"]
                if spinner_state["index"] < len(spinner_labels)
                else len(spinner_labels) - 1
            )
            label = spinner_labels[label_index]
            sys.stderr.write(f"\r{frame} {label}\033[K")
            sys.stderr.flush()
            spinner_state["index"] += 1
            stop_event.wait(0.7)
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    thread = threading.Thread(target=_spinner, daemon=True)
    thread.start()
    try:
        result = _run_subprocess_with_active_tracking(command, prompt, timeout)
    finally:
        stop_event.set()
        thread.join(timeout=1.0)

    log_path = fn_write_log(
        log_dir=log_dir,
        task_id=task_id or "target",
        target=command[0] if command else "target",
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        returncode=result.returncode,
    )
    return result, log_path


def main(argv: list[str] | None = None) -> int:
    sub = _get_pkg_attr("subprocess", subprocess)
    time_mod = _get_pkg_attr("time", time)
    path_cls = _get_pkg_attr("Path", Path)
    fn_acquire_lock = _get_pkg_attr("_acquire_lock", _acquire_lock)
    fn_release_lock = _get_pkg_attr("_release_lock", _release_lock)
    fn_update_lock_daemon = _get_pkg_attr("_update_lock_for_daemon_child", _update_lock_for_daemon_child)
    fn_load_manifest = _get_pkg_attr("_load_manifest", _load_manifest)
    fn_normalize_manifest = _get_pkg_attr("_normalize_host_manifest", _normalize_host_manifest)

    status_data = {
        "task_id": "",
        "schedule_id": None,
        "target": None,
        "model": None,
        "stage": "prepare",
        "manifest_path": None,
        "source_image_path": None,
        "output_path": None,
        "target_log_path": None,
        "recovery_attempted": False,
        "recovered_from": None,
        "artifact_dir": None,
        "output_image": None,
        "error": None,
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
    if args.model:
        if args.target == "schedule":
            sys.stderr.write("Error: --model option is not supported for target 'schedule'\n")
            return 1
        if args.target == "agy":
            get_agy = _get_pkg_attr("_get_agy_models", _get_agy_models)
            available_models = get_agy()
            if available_models and args.model not in available_models:
                sys.stderr.write(
                    f"Error: Model '{args.model}' is not available for target 'agy'.\n"
                    f"Available models: {', '.join(available_models)}\n"
                )
                return 1
        elif args.target == "codex":
            get_codex = _get_pkg_attr("_get_codex_models", _get_codex_models)
            available_models = get_codex()
            if available_models and args.model not in available_models:
                sys.stderr.write(
                    f"Error: Model '{args.model}' is not available for target 'codex'.\n"
                    f"Available models: {', '.join(available_models)}\n"
                )
                return 1

    project_dir = path_cls(args.project_dir)
    if args.manifest_path:
        manifest_path = path_cls(args.manifest_path)
    else:
        random_suffix = uuid.uuid4().hex[:8]
        manifest_path = (
            path_cls("data") / f"dailyfx-run-{random_suffix}.json"
        )
    shared_manifest_path = manifest_path
    backend_command = _build_backend_command(args)

    if args.list_schedules:
        try:
            backend_run = sub.run(
                backend_command,
                cwd=project_dir,
                text=True,
                capture_output=True,
                check=False,
                timeout=_LIST_SCHEDULES_TIMEOUT,
            )
        except sub.TimeoutExpired:
            sys.stderr.write(f"Error: --list-schedules timed out after {_LIST_SCHEDULES_TIMEOUT}s\n")
            return 124
        if backend_run.returncode != 0:
            if backend_run.stderr:
                sys.stderr.write(backend_run.stderr)
            elif backend_run.stdout:
                sys.stderr.write(backend_run.stdout)
            return backend_run.returncode or 1
        sys.stdout.write(backend_run.stdout)
        return 0

    if args.list_models:
        if args.target is None:
            sys.stderr.write("target is required with --list-models\n")
            return 1
        if args.target == "schedule":
            sys.stderr.write("Error: target 'schedule' does not support listing models (models are defined by backend presets)\n")
            return 1
        _print_model_list_header(args.target)
        if args.target == "agy":
            list_agy = _get_pkg_attr("_list_agy_models", _list_agy_models)
            return list_agy()
        list_codex = _get_pkg_attr("_list_codex_models", _list_codex_models)
        return list_codex()

    if not (args.list_schedules or args.status or args.stop or args.doctor or args.clean_manifests):
        if args.schedule_id is None or args.target is None:
            sys.stderr.write(
                "schedule-id and target are required unless --list-schedules is used\n"
            )
            return 1

    if args.clean_manifests:
        return _handle_clean_manifests()

    if args.doctor:
        return _handle_doctor(args)

    if args.status:
        return _handle_status(args)

    if args.stop:
        return _handle_stop(args)

    if args.dry_run:
        target_preview = _target_prefix(args.target, args.model)
        _print_command("backend", backend_command)
        _print_command(
            "manifest", ["write", str(manifest_path), "and", str(shared_manifest_path)]
        )
        _print_command(
            "target",
            target_preview
            + shlex.split(
                (
                    args.agy_command_template
                    if args.target == "agy"
                    else args.codex_command_template
                ).format(
                    image_path="{image_path}",
                    manifest_path="{manifest_path}",
                    output_path="{output_path}",
                    prompt="{prompt}",
                )
            ),
        )
        _print_command(
            "finalize",
            [
                "docker",
                "compose",
                "-f",
                args.compose_file,
                "exec",
                "-T",
                args.service,
                "dailyfx",
                "finalize-host",
                "--manifest-path",
                f"/data/{shared_manifest_path.name}",
            ],
        )
        _print_note("Dry-run does not execute docker compose or the host tool.")
        return 0

    repeat = max(1, args.repeat)
    last_exit = 0
    pid_file = None

    if args.schedule_id is not None and args.target is not None:
        try:
            fn_acquire_lock(args.schedule_id, args.target)
        except RuntimeError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1

    if args.daemon:
        if args.pid_file:
            pid_file = path_cls(args.pid_file)
        else:
            target_str = args.target if args.target else "default"
            sched_str = (
                f"s{args.schedule_id}" if args.schedule_id is not None else "default"
            )
            pid_file = path_cls("data") / f"dailyfx-agent-{sched_str}-{target_str}.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        log_file_path = path_cls("data") / "logs" / "agent" / f"{pid_file.stem}.log"
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        startup_read_fd, startup_write_fd = os.pipe()
        pid = os.fork()
        if pid > 0:
            os.close(startup_write_fd)
            startup_ok = False
            try:
                ready, _, _ = select.select(
                    [startup_read_fd], [], [], _DAEMON_STARTUP_TIMEOUT
                )
                if ready:
                    startup_ok = os.read(startup_read_fd, 1) == b"1"
            finally:
                os.close(startup_read_fd)

            if not startup_ok:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass
                pid_file.unlink(missing_ok=True)
                pid_file.with_name(pid_file.name + ".json").unlink(missing_ok=True)
                if args.schedule_id is not None and args.target is not None:
                    fn_release_lock(args.schedule_id, args.target)
                sys.stderr.write("Error: daemon failed to start\n")
                return 1

            non_local_lock_release = True
            if args.schedule_id is not None and args.target is not None:
                fn_update_lock_daemon(args.schedule_id, args.target, pid)

            print(f"daemon started: pid={pid} pidfile={pid_file}")
            return 0
        os.close(startup_read_fd)
        try:
            os.umask(0o077)
            os.setsid()

            metadata_file = pid_file.with_name(pid_file.name + ".json")
            metadata = {
                "pid": os.getpid(),
                "schedule_id": args.schedule_id,
                "target": args.target,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "log_path": str(log_file_path.resolve()),
                "manifest_path": str(manifest_path.resolve()),
            }
            _atomic_write_text(pid_file, f"{os.getpid()}\n")
            _atomic_write_text(
                metadata_file,
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            )
            try:
                os.write(startup_write_fd, b"1")
            except OSError:
                pass
        except BaseException:
            pid_file.unlink(missing_ok=True)
            pid_file.with_name(pid_file.name + ".json").unlink(missing_ok=True)
            try:
                os.write(startup_write_fd, b"0")
            except OSError:
                pass
            raise
        finally:
            os.close(startup_write_fd)

        try:
            sys.stdout.flush()
            sys.stderr.flush()
            log_fd = os.open(str(log_file_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            devnull = os.open(os.devnull, os.O_RDONLY)
            os.dup2(devnull, 0)
            os.dup2(log_fd, 1)
            os.dup2(log_fd, 2)
            os.close(devnull)
            os.close(log_fd)
        except OSError:
            pass
        sys.stdin = open(os.devnull, "r")
        sys.stdout = open(str(log_file_path), "a")
        sys.stderr = open(str(log_file_path), "a")

    try:
        for run_index in range(1, repeat + 1):
            if repeat > 1:
                print(f"--- run {run_index}/{repeat} ---")

            if args.manifest_path:
                if run_index == 1:
                    manifest_path = path_cls(args.manifest_path)
                else:
                    path_obj = path_cls(args.manifest_path)
                    manifest_path = path_obj.with_name(f"{path_obj.stem}-run{run_index}{path_obj.suffix}")
                    sys.stderr.write(
                        f"warning: using modified manifest path for repeat run {run_index}: {manifest_path}\n"
                    )
            else:
                random_suffix = uuid.uuid4().hex[:8]
                manifest_path = path_cls("data") / f"dailyfx-run-{random_suffix}.json"
            shared_manifest_path = manifest_path

            # 1. PREPARE STAGE
            status_data["stage"] = "prepare" if args.target != "schedule" else "generate"
            if args.target == "schedule" and not args.json_status:
                print("Executing schedule generation on the backend...")
            try:
                backend_run = sub.run(
                    backend_command,
                    cwd=project_dir,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=args.timeout,
                )
                if backend_run.returncode != 0:
                    err_msg = (backend_run.stderr or backend_run.stdout or f"exit code {backend_run.returncode}").strip()
                    raise RuntimeError(f"Backend prepare command failed: {err_msg}")
            except Exception as e:
                status_data["error"] = str(e)
                last_exit = 1
                if args.debug:
                    import traceback
                    traceback.print_exc()
                else:
                    sys.stderr.write(f"Error: {e}\n")
                continue

            # 2. MANIFEST LOAD STAGE
            status_data["stage"] = "manifest load"
            status_data["manifest_path"] = str(manifest_path.resolve())
            try:
                manifest_path.parent.mkdir(parents=True, exist_ok=True)
                manifest_path.write_text(backend_run.stdout, encoding="utf-8")
                if shared_manifest_path != manifest_path:
                    shared_manifest_path.parent.mkdir(parents=True, exist_ok=True)
                    shared_manifest_path.write_text(backend_run.stdout, encoding="utf-8")
                manifest = fn_load_manifest(manifest_path)
            except Exception as e:
                status_data["error"] = str(e)
                last_exit = 1
                if args.debug:
                    import traceback
                    traceback.print_exc()
                else:
                    sys.stderr.write(f"Error loading manifest: {e}\n")
                continue

            if args.target == "schedule":
                status_data["stage"] = "completed"
                output_path = manifest.get("image_path") or ""
                status_data["output_path"] = str(path_cls(output_path).resolve()) if output_path else ""
                if not args.json_status:
                    print(f"done: {output_path}")
                continue

            if args.verbose:
                _print_manifest(manifest)

            task_id = str(manifest.get("task_id") or "").strip() or "target"
            status_data["task_id"] = task_id
            artifact_dir = _task_artifact_dir(task_id)
            status_data["artifact_dir"] = str(artifact_dir.resolve())
            _write_task_json_artifact(task_id, "manifest.before.json", manifest)
            prompt = str(
                manifest.get("prompt") or manifest.get("handoff_prompt") or ""
            ).strip()
            if not prompt:
                status_data["error"] = "Backend manifest did not include prompt"
                last_exit = 1
                sys.stderr.write("Backend manifest did not include prompt\n")
                continue

            task_trace = manifest.get("task_trace")
            if not isinstance(task_trace, list):
                config_json = manifest.get("config_json")
                if isinstance(config_json, dict):
                    task_trace = config_json.get("task_trace")
            trace_labels = _task_trace_labels(task_trace)
            if not args.json_status:
                print(f"image provider: {args.target}")

            try:
                image_path = str(
                    manifest.get("source_image_path")
                    or manifest.get("host_relative_image_path")
                    or ""
                ).strip()
                if not image_path:
                    image_path = _container_to_host_image_path(
                        str(manifest.get("image_path") or "")
                    )
                elif image_path.startswith("/data/"):
                    image_path = _container_to_host_image_path(image_path)
            except ValueError as exc:
                status_data["error"] = str(exc)
                sys.stderr.write(f"{exc}\n")
                last_exit = 1
                continue

            if not image_path:
                status_data["error"] = "Backend manifest did not include source_image_path"
                sys.stderr.write("Backend manifest did not include source_image_path\n")
                last_exit = 1
                continue

            status_data["source_image_path"] = str(path_cls(image_path).resolve())

            output_path = str(
                manifest.get("output_path") or manifest.get("image_path") or ""
            ).strip()
            if output_path.startswith("/data/"):
                try:
                    output_path = _container_to_host_image_path(output_path)
                except ValueError as exc:
                    status_data["error"] = str(exc)
                    sys.stderr.write(f"{exc}\n")
                    last_exit = 1
                    continue

            if not output_path:
                status_data["error"] = "Backend manifest did not include output_path"
                sys.stderr.write("Backend manifest did not include output_path\n")
                last_exit = 1
                continue

            status_data["output_path"] = str(path_cls(output_path).resolve())

            abs_image_path = str(path_cls(image_path).resolve())
            abs_output_path = str(path_cls(output_path).resolve())
            abs_manifest_path = str(manifest_path.resolve())
            fn_augment_prompt = _get_pkg_attr("_augment_host_prompt", _augment_host_prompt)
            prompt = fn_augment_prompt(
                prompt,
                abs_image_path,
                abs_manifest_path,
                abs_output_path,
                task_id,
            )
            _write_task_text_artifact(task_id, "prompt.txt", prompt)

            target_command = _build_target_command(
                args.target,
                image_path,
                str(manifest_path),
                output_path,
                args.model,
                prompt,
                agy_template=args.agy_command_template,
                codex_template=args.codex_command_template,
            )

            target_start_time = time_mod.time()

            # 3. TARGET RUN STAGE
            status_data["stage"] = "target run"
            try:
                fn_run_spinner = _get_pkg_attr("_run_target_with_spinner", _run_target_with_spinner)
                target_run, target_log_path = fn_run_spinner(
                    target_command,
                    prompt=prompt,
                    task_id=task_id,
                    labels=trace_labels,
                    timeout=args.timeout,
                    daemon_mode=args.daemon,
                )
                status_data["target_log_path"] = str(path_cls(target_log_path).resolve()) if target_log_path else None
                if target_log_path:
                    _copy_task_artifact(task_id, path_cls(target_log_path), "target.log")
                if target_run.returncode != 0:
                    err_msg = (target_run.stderr or target_run.stdout or f"exit code {target_run.returncode}").strip()
                    raise RuntimeError(f"Target tool '{args.target}' failed: {err_msg}")
            except Exception as e:
                status_data["error"] = str(e)
                last_exit = 1
                if args.debug:
                    import traceback
                    traceback.print_exc()
                else:
                    sys.stderr.write(f"Error during target execution: {e}\n")
                continue

            # 4. METADATA VALIDATION STAGE
            status_data["stage"] = "metadata validation"
            try:
                updated_manifest = fn_normalize_manifest(
                    fn_load_manifest(manifest_path), manifest
                )
                manifest_path.write_text(
                    json.dumps(updated_manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                _write_task_json_artifact(task_id, "manifest.after.json", updated_manifest)
            except Exception as e:
                status_data["error"] = str(e)
                last_exit = 1
                if args.debug:
                    import traceback
                    traceback.print_exc()
                else:
                    sys.stderr.write(f"Metadata validation failed: {e}\n")
                continue

            output_file = path_cls(output_path)
            if not output_file.is_absolute():
                output_file = project_dir / output_file
            if not output_file.exists():
                # 5. RECOVERY STAGE
                status_data["stage"] = "recovery"
                status_data["recovery_attempted"] = True
                try:
                    generated_image = None
                    missing_message = None
                    if args.target == "codex":
                        find_codex = _get_pkg_attr("_find_latest_codex_image", _find_latest_codex_image)
                        generated_image = find_codex(
                            target_start_time,
                            task_id=task_id,
                            notes_to_stderr=args.json_status,
                        )
                        missing_message = f"codex finished without creating {output_path} or a new image under ~/.codex/generated_images"
                    elif args.target == "agy":
                        find_agy = _get_pkg_attr("_find_latest_agy_image", _find_latest_agy_image)
                        generated_image = find_agy(
                            target_start_time,
                            task_id=task_id,
                            notes_to_stderr=args.json_status,
                        )
                        missing_message = f"agy finished without creating {output_path} or a new image under ~/.gemini/antigravity-cli/brain"

                    if generated_image is not None:
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        output_file.write_bytes(generated_image.read_bytes())
                        recovered_from = str(generated_image.resolve())
                        status_data["recovered_from"] = recovered_from
                        updated_manifest_config = updated_manifest.get("config_json")
                        if not isinstance(updated_manifest_config, dict):
                            updated_manifest_config = {}
                        updated_manifest["config_json"] = {
                            **updated_manifest_config,
                            "recovered_from": recovered_from,
                        }
                        manifest_path.write_text(
                            json.dumps(updated_manifest, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8",
                        )
                        _write_task_json_artifact(task_id, "manifest.after.json", updated_manifest)
                    else:
                        raise RuntimeError(missing_message)
                except Exception as e:
                    status_data["error"] = str(e)
                    last_exit = 1
                    if args.debug:
                        import traceback
                        traceback.print_exc()
                    else:
                        sys.stderr.write(f"Image recovery failed: {e}\n")
                    continue

            try:
                output_details = _validate_output_image(output_file)
                status_data["output_image"] = output_details
            except Exception as e:
                status_data["stage"] = "output validation"
                status_data["error"] = str(e)
                last_exit = 1
                if args.debug:
                    import traceback
                    traceback.print_exc()
                else:
                    sys.stderr.write(f"Output validation failed: {e}\n")
                continue

            if shared_manifest_path != manifest_path:
                try:
                    if manifest_path.exists():
                        shared_manifest_path.write_text(
                            manifest_path.read_text(encoding="utf-8"), encoding="utf-8"
                        )
                except Exception as exc:
                    sys.stderr.write(
                        f"warning: failed to sync manifest changes to shared manifest: {exc}\n"
                    )

            finalize_command = [
                "docker",
                "compose",
                "-f",
                args.compose_file,
                "exec",
                "-T",
                args.service,
                "dailyfx",
                "finalize-host",
                "--manifest-path",
                f"/data/{shared_manifest_path.name}",
            ]

            # 6. FINALIZE STAGE
            status_data["stage"] = "finalize"
            try:
                finalize_run = sub.run(
                    finalize_command,
                    cwd=project_dir,
                    check=False,
                    text=True,
                    capture_output=True,
                    timeout=args.timeout,
                )
                if finalize_run.returncode != 0:
                    err_msg = (finalize_run.stderr or finalize_run.stdout or f"exit code {finalize_run.returncode}").strip()
                    raise RuntimeError(f"Finalize command failed: {err_msg}")
            except Exception as e:
                status_data["error"] = str(e)
                last_exit = 1
                if args.debug:
                    import traceback
                    traceback.print_exc()
                else:
                    sys.stderr.write(f"Finalization failed: {e}\n")
                continue

            status_data["stage"] = "completed"
            if not args.json_status:
                print(f"done: {output_path}")
                if args.verbose:
                    print(f"log: {target_log_path}")

    finally:
        if not args.keep_manifest:
            if "manifest_path" in locals() and manifest_path:
                if not args.manifest_path or manifest_path.name.startswith("dailyfx-run-"):
                    manifest_path.unlink(missing_ok=True)
            if (
                "shared_manifest_path" in locals()
                and shared_manifest_path != manifest_path
            ):
                shared_manifest_path.unlink(missing_ok=True)
        if args.daemon and pid_file:
            pid_file.unlink(missing_ok=True)
            pid_file.with_name(pid_file.name + ".json").unlink(missing_ok=True)
        if args.schedule_id is not None and args.target is not None:
            if not locals().get("non_local_lock_release", False):
                fn_release_lock(args.schedule_id, args.target)
        if status_data.get("task_id"):
            _write_task_json_artifact(str(status_data["task_id"]), "status.json", status_data)
        if "args" in locals() and getattr(args, "json_status", False):
            print(json.dumps(status_data, ensure_ascii=False, indent=2))

    return last_exit
