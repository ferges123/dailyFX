from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import dailyfx_agent.runner as runner


def _recover_target_output(
    *,
    target: str,
    target_start_time: float,
    task_id: str,
    output_file: Path,
    manifest: dict[str, object],
    status_data: dict[str, object],
    notes_to_stderr: bool,
    strict_recovery: bool,
) -> dict[str, object]:
    if output_file.exists():
        return manifest

    status_data["stage"] = "recovery"
    status_data["recovery_attempted"] = True
    if target == "codex":
        generated_image = runner._find_latest_codex_image(
            target_start_time, task_id=task_id,
            notes_to_stderr=notes_to_stderr, strict=strict_recovery,
        )
        missing_message = (
            f"codex finished without creating {output_file} or a new image under ~/.codex/generated_images"
        )
    else:
        generated_image = runner._find_latest_agy_image(
            target_start_time, task_id=task_id,
            notes_to_stderr=notes_to_stderr, strict=strict_recovery,
        )
        missing_message = (
            f"agy finished without creating {output_file} or a new image under ~/.gemini/antigravity-cli/brain"
        )

    if generated_image is None:
        raise RuntimeError(missing_message)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(generated_image.read_bytes())
    recovered_from = str(generated_image.resolve())
    status_data["recovered_from"] = recovered_from
    config_json = manifest.get("config_json")
    if not isinstance(config_json, dict):
        config_json = {}
    manifest["config_json"] = {**config_json, "recovered_from": recovered_from}
    return manifest


def _mark_host_task_failed(subprocess_module, args, task_id: str, error: str) -> None:
    command = [
        "docker",
        "compose",
        "-f",
        args.compose_file,
        "exec",
        "-T",
        args.service,
        "dailyfx",
        "fail-host",
        "--task-id",
        task_id,
        "--error",
        error[:2000],
    ]
    try:
        result = subprocess_module.run(
            command,
            cwd=args.project_dir,
            check=False,
            text=True,
            capture_output=True,
            timeout=min(args.timeout, 30),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "no output").strip()
            sys.stderr.write(
                f"warning: fail-host returned exit code {result.returncode} for task {task_id}: {detail}\n"
            )
    except Exception as exc:
        sys.stderr.write(f"warning: fail-host reporting failed for task {task_id}: {exc}\n")


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
    if daemon_mode:
        result = runner._run_subprocess_with_active_tracking(command, prompt, timeout)

        log_path = runner._write_target_log(
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
        result = runner._run_subprocess_with_active_tracking(command, prompt, timeout)
    finally:
        stop_event.set()
        thread.join(timeout=1.0)
        if thread.is_alive():
            sys.stderr.write("warning: spinner thread did not stop within 1 second\n")

    log_path = runner._write_target_log(
        log_dir=log_dir,
        task_id=task_id or "target",
        target=command[0] if command else "target",
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        returncode=result.returncode,
    )
    return result, log_path


def _handle_command_mode(args: argparse.Namespace) -> int | None:
    if args.list_schedules:
        backend_command = runner._build_backend_command(args)
        try:
            backend_run = subprocess.run(
                backend_command,
                cwd=Path(args.project_dir),
                text=True,
                capture_output=True,
                check=False,
                timeout=runner._LIST_SCHEDULES_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            sys.stderr.write(f"Error: --list-schedules timed out after {runner._LIST_SCHEDULES_TIMEOUT}s\n")
            return 124
        if backend_run.returncode != 0:
            sys.stderr.write(backend_run.stderr or backend_run.stdout)
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
        runner._print_model_list_header(args.target)
        if args.target == "agy":
            return runner._list_agy_models()
        return runner._list_codex_models()

    if args.clean_manifests:
        return runner._handle_clean_manifests()

    if args.doctor:
        return runner._handle_doctor(args)

    if args.status:
        return runner._handle_status(args)

    if args.stop:
        return runner._handle_stop(args)

    return None


def _validate_model(args: argparse.Namespace) -> int | None:
    if not args.model:
        return None
    if args.target == "schedule":
        sys.stderr.write("Error: --model option is not supported for target 'schedule'\n")
        return 1
    if args.target == "agy":
        available_models = runner._get_agy_models()
        if available_models and args.model not in available_models:
            sys.stderr.write(
                f"Error: Model '{args.model}' is not available for target 'agy'.\n"
                f"Available models: {', '.join(available_models)}\n"
            )
            return 1
    elif args.target == "codex":
        available_models = runner._get_codex_models()
        if available_models and args.model not in available_models:
            sys.stderr.write(
                f"Error: Model '{args.model}' is not available for target 'codex'.\n"
                f"Available models: {', '.join(available_models)}\n"
            )
            return 1
    return None


def _manifest_path_for_run(args: argparse.Namespace, run_index: int, first_manifest: Path | None) -> Path:
    if args.manifest_path:
        if run_index == 1:
            return Path(args.manifest_path)
        path_obj = Path(args.manifest_path)
        new_path = path_obj.with_name(f"{path_obj.stem}-run{run_index}{path_obj.suffix}")
        sys.stderr.write(f"warning: using modified manifest path for repeat run {run_index}: {new_path}\n")
        return new_path
    random_suffix = uuid.uuid4().hex[:8]
    return Path("data") / f"dailyfx-run-{random_suffix}.json"


def _run_backend_command(command: list[str], project_dir: Path, timeout: int) -> str:
    result = subprocess.run(
        command,
        cwd=project_dir,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        err_msg = (result.stderr or result.stdout or f"exit code {result.returncode}").strip()
        raise RuntimeError(f"Backend prepare command failed: {err_msg}")
    return result.stdout


def _resolve_source_image(manifest: dict[str, object]) -> str:
    image_path = str(
        manifest.get("source_image_path")
        or manifest.get("host_relative_image_path")
        or ""
    ).strip()
    if not image_path:
        image_path = runner._container_to_host_image_path(
            str(manifest.get("image_path") or "")
        )
    elif image_path.startswith("/data/"):
        image_path = runner._container_to_host_image_path(image_path)
    if not image_path:
        raise ValueError("Backend manifest did not include source_image_path")
    return image_path


def _resolve_output_path(manifest: dict[str, object]) -> str:
    output_path = str(
        manifest.get("output_path") or manifest.get("image_path") or ""
    ).strip()
    if output_path.startswith("/data/"):
        output_path = runner._container_to_host_image_path(output_path)
    if not output_path:
        raise ValueError("Backend manifest did not include output_path")
    return output_path


def _handle_dry_run(args: argparse.Namespace, manifest_path: Path, shared_manifest_path: Path) -> int:
    backend_command = runner._build_backend_command(args)
    runner._print_command("backend", backend_command)
    runner._print_command("manifest", ["write", str(manifest_path), "and", str(shared_manifest_path)])
    runner._print_command(
        "target",
        runner._build_target_command(
            args.target,
            "{image_path}",
            "{manifest_path}",
            "{output_path}",
            args.model,
            "{prompt}",
            agy_template=args.agy_command_template,
            codex_template=args.codex_command_template,
        ),
    )
    runner._print_command(
        "finalize",
        [
            "docker", "compose", "-f", args.compose_file,
            "exec", "-T", args.service, "dailyfx",
            "finalize-host", "--manifest-path", f"/data/{shared_manifest_path.name}",
        ],
    )
    runner._print_note("Dry-run does not execute docker compose or the host tool.")
    return 0


def _run_workflow_iteration(
    args: argparse.Namespace,
    backend_command: list[str],
    project_dir: Path,
    manifest_path: Path,
    shared_manifest_path: Path,
    status_data: dict[str, object],
) -> int:
    # 1. PREPARE STAGE
    status_data["stage"] = "prepare" if args.target != "schedule" else "generate"
    if args.target == "schedule" and not args.json_status:
        print("Executing schedule generation on the backend...")
    try:
        backend_stdout = runner._run_backend_command(backend_command, project_dir, args.timeout)
    except Exception as e:
        status_data["error"] = str(e)
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            sys.stderr.write(f"Error: {e}\n")
        return 1

    # 2. MANIFEST LOAD STAGE
    status_data["stage"] = "manifest load"
    status_data["manifest_path"] = str(manifest_path.resolve())
    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(backend_stdout, encoding="utf-8")
        if shared_manifest_path != manifest_path:
            shared_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            shared_manifest_path.write_text(backend_stdout, encoding="utf-8")
        manifest = runner._load_manifest(manifest_path)
    except Exception as e:
        status_data["error"] = str(e)
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            sys.stderr.write(f"Error loading manifest: {e}\n")
        return 1

    if args.target == "schedule":
        status_data["stage"] = "completed"
        output_path_s = manifest.get("image_path") or ""
        status_data["output_path"] = str(Path(output_path_s).resolve()) if output_path_s else ""
        if not args.json_status:
            print(f"done: {output_path_s}")
        return 0

    if args.verbose:
        runner._print_manifest(manifest)

    task_id = str(manifest.get("task_id") or "").strip() or "target"
    original_manifest = dict(manifest)
    status_data["task_id"] = task_id
    artifact_dir = runner._task_artifact_dir(task_id)
    status_data["artifact_dir"] = str(artifact_dir.resolve())

    runner._write_task_json_artifact(task_id, "manifest.before.json", manifest)
    prompt = str(manifest.get("prompt") or manifest.get("handoff_prompt") or "").strip()
    if not prompt:
        status_data["error"] = "Backend manifest did not include prompt"
        runner._mark_host_task_failed(subprocess, args, task_id, status_data["error"])
        sys.stderr.write("Backend manifest did not include prompt\n")
        return 1

    task_trace = manifest.get("task_trace")
    if not isinstance(task_trace, list):
        config_json = manifest.get("config_json")
        if isinstance(config_json, dict):
            task_trace = config_json.get("task_trace")
    trace_labels = runner._task_trace_labels(task_trace)
    if not args.json_status:
        print(f"image provider: {args.target}")

    try:
        image_path = runner._resolve_source_image(manifest)
    except ValueError as exc:
        status_data["error"] = str(exc)
        runner._mark_host_task_failed(subprocess, args, task_id, str(exc))
        sys.stderr.write(f"{exc}\n")
        return 1

    status_data["source_image_path"] = str(Path(image_path).resolve())

    try:
        output_path = runner._resolve_output_path(manifest)
    except ValueError as exc:
        status_data["error"] = str(exc)
        runner._mark_host_task_failed(subprocess, args, task_id, str(exc))
        sys.stderr.write(f"{exc}\n")
        return 1

    status_data["output_path"] = str(Path(output_path).resolve())

    abs_image_path = str(Path(image_path).resolve())
    abs_output_path = str(Path(output_path).resolve())
    abs_manifest_path = str(manifest_path.resolve())
    augmented_prompt = runner._augment_host_prompt(prompt, abs_image_path, abs_manifest_path, abs_output_path, task_id)
    runner._write_task_text_artifact(task_id, "prompt.txt", augmented_prompt)

    target_command = runner._build_target_command(
        args.target, image_path, str(manifest_path), output_path,
        args.model, augmented_prompt,
        agy_template=args.agy_command_template,
        codex_template=args.codex_command_template,
    )

    target_start_time = time.time()

    # 3. TARGET RUN STAGE
    status_data["stage"] = "target run"
    try:
        target_run, target_log_path = runner._run_target_with_spinner(
            target_command, prompt=augmented_prompt,
            task_id=task_id, labels=trace_labels,
            timeout=args.timeout, daemon_mode=args.daemon,
        )
        status_data["target_log_path"] = str(Path(target_log_path).resolve()) if target_log_path else None
        if target_log_path:
            runner._copy_task_artifact(task_id, Path(target_log_path), "target.log")
        if target_run.returncode != 0:
            err_msg = (target_run.stderr or target_run.stdout or f"exit code {target_run.returncode}").strip()
            raise RuntimeError(f"Target tool '{args.target}' failed: {err_msg}")
        target_text = f"{target_run.stdout or ''}\n{target_run.stderr or ''}"
        if re.search(r"soft-denying|auto-denied|command permission", target_text, re.IGNORECASE):
            raise RuntimeError(f"Target tool '{args.target}' denied a command permission: {target_text.strip()}")
    except Exception as e:
        status_data["error"] = str(e)
        runner._mark_host_task_failed(subprocess, args, task_id, str(e))
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            sys.stderr.write(f"Error during target execution: {e}\n")
        return 1

    # 4. METADATA VALIDATION STAGE
    output_file = Path(output_path)
    if not output_file.is_absolute():
        output_file = project_dir / output_file
    try:
        try:
            target_manifest = runner._load_manifest(manifest_path)
            if isinstance(target_manifest, dict):
                manifest = {**manifest, **target_manifest}
        except Exception:
            try:
                partial_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(partial_manifest, dict):
                    manifest = {**manifest, **partial_manifest}
            except (OSError, json.JSONDecodeError):
                pass
        manifest = runner._recover_target_output(
            target=args.target, target_start_time=target_start_time,
            task_id=task_id, output_file=output_file,
            manifest=manifest, status_data=status_data,
            notes_to_stderr=args.json_status,
            strict_recovery=args.strict_recovery,
        )
        if status_data.get("recovered_from"):
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    except Exception as e:
        status_data["error"] = str(e)
        runner._mark_host_task_failed(subprocess, args, task_id, str(e))
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            sys.stderr.write(f"Image recovery failed: {e}\n")
        return 1

    status_data["stage"] = "metadata validation"
    try:
        updated_manifest = runner._normalize_host_manifest(runner._load_manifest(manifest_path), original_manifest)
        manifest_path.write_text(
            json.dumps(updated_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        runner._write_task_json_artifact(task_id, "manifest.after.json", updated_manifest)
    except Exception as e:
        status_data["error"] = str(e)
        runner._mark_host_task_failed(subprocess, args, task_id, str(e))
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            sys.stderr.write(f"Metadata validation failed: {e}\n")
        return 1

    try:
        output_details = runner._validate_output_image(output_file)
        status_data["output_image"] = output_details
    except Exception as e:
        status_data["stage"] = "output validation"
        status_data["error"] = str(e)
        runner._mark_host_task_failed(subprocess, args, task_id, str(e))
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            sys.stderr.write(f"Output validation failed: {e}\n")
        return 1

    if shared_manifest_path != manifest_path:
        try:
            if manifest_path.exists():
                shared_manifest_path.write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception as exc:
            sys.stderr.write(f"warning: failed to sync manifest changes to shared manifest: {exc}\n")

    finalize_command = [
        "docker", "compose", "-f", args.compose_file,
        "exec", "-T", args.service, "dailyfx",
        "finalize-host", "--manifest-path", f"/data/{shared_manifest_path.name}",
    ]

    # 5. FINALIZE STAGE
    status_data["stage"] = "finalize"
    try:
        finalize_run = subprocess.run(
            finalize_command, cwd=project_dir,
            check=False, text=True, capture_output=True,
            timeout=args.timeout,
        )
        if finalize_run.returncode != 0:
            err_msg = (finalize_run.stderr or finalize_run.stdout or f"exit code {finalize_run.returncode}").strip()
            raise RuntimeError(f"Finalize command failed: {err_msg}")
    except Exception as e:
        status_data["error"] = str(e)
        runner._mark_host_task_failed(subprocess, args, task_id, str(e))
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            sys.stderr.write(f"Finalization failed: {e}\n")
        return 1

    status_data["stage"] = "completed"
    if not args.json_status:
        print(f"done: {output_path}")
        if args.verbose:
            print(f"log: {target_log_path}")
    return 0
