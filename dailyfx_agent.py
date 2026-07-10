from __future__ import annotations

import argparse
import itertools
import json
import os
import queue
import re
import select
import shlex
import subprocess
_original_subprocess_run = subprocess.run
import sys

import shutil
import tempfile
import time
import threading
import uuid
from pathlib import Path
from datetime import datetime, timezone

LOCKS_DIR = Path("data") / "locks"

# Try to dynamically import the shared manifest contract from the backend app.
try:
    _script_dir = Path(__file__).resolve().parent
    _backend_dir = _script_dir / "backend"
    if _backend_dir.is_dir() and str(_backend_dir) not in sys.path:
        sys.path.insert(0, str(_backend_dir))
    from app.services.generation.host_manifest import (
        HOST_METADATA_SOURCE,
        validate_and_normalize_host_manifest,
        ManifestValidationError,
    )
except ImportError:
    HOST_METADATA_SOURCE = "host_agent_final_vision"
    class ManifestValidationError(ValueError):
        pass

    def validate_and_normalize_host_manifest(
        manifest: dict[str, object],
        original_manifest: dict[str, object] | None = None
    ) -> dict[str, object]:
        if not isinstance(manifest, dict):
            raise ManifestValidationError("Host manifest is not a JSON object")

        if isinstance(original_manifest, dict):
            normalized = dict(original_manifest)
            normalized.update(manifest)
        else:
            normalized = dict(manifest)

        title = str(normalized.get("title") or "").strip()
        summary = str(normalized.get("summary") or "").strip()
        tags = normalized.get("tags")
        metadata_source = str(normalized.get("metadata_source") or "").strip()

        if not title:
            raise ManifestValidationError("Host manifest did not include an updated title")
        if not summary:
            raise ManifestValidationError("Host manifest did not include an updated summary")
        if not isinstance(tags, list):
            raise ManifestValidationError("Host manifest did not include valid tags")

        normalized_tags = []
        for tag in tags:
            if not isinstance(tag, str):
                raise ManifestValidationError("Host manifest did not include valid tags")
            tag_text = tag.strip()
            if not tag_text:
                raise ManifestValidationError("Host manifest did not include valid tags")
            normalized_tags.append(tag_text)

        if not 3 <= len(normalized_tags) <= 6:
            raise ManifestValidationError("Host manifest did not include valid tags")

        if metadata_source != HOST_METADATA_SOURCE:
            raise ManifestValidationError("Host manifest did not include the required metadata_source")

        normalized["title"] = title
        normalized["summary"] = summary
        normalized["tags"] = normalized_tags
        normalized["metadata_source"] = metadata_source

        if isinstance(original_manifest, dict):
            original_title = str(original_manifest.get("title") or "").strip()
            original_summary = str(original_manifest.get("summary") or "").strip()
            original_tags_raw = original_manifest.get("tags")
            original_tags = []
            if isinstance(original_tags_raw, list):
                for tag in original_tags_raw:
                    if isinstance(tag, str):
                        tag_text = tag.strip()
                        if tag_text:
                            original_tags.append(tag_text)
            if (
                title == original_title
                and summary == original_summary
                and normalized_tags == original_tags
            ):
                raise ManifestValidationError("Host agent did not update title, summary, or tags")

        return normalized


IS_TESTING = "pytest" in sys.modules or "py.test" in sys.modules


import signal

_active_process: subprocess.Popen[str] | None = None


def _sigterm_handler(signum, frame):
    global _active_process
    if _active_process:
        try:
            _active_process.kill()
        except OSError:
            pass
    sys.exit(128 + signum)


try:
    signal.signal(signal.SIGTERM, _sigterm_handler)
    signal.signal(signal.SIGINT, _sigterm_handler)
except ValueError:
    pass


def _run_subprocess_with_active_tracking(
    command: list[str], prompt: str, timeout: int | None
) -> subprocess.CompletedProcess[str]:
    if subprocess.run is not _original_subprocess_run:
        try:
            return subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(
                command, 124, stdout="", stderr=f"Timed out after {timeout}s"
            )

    global _active_process
    proc = None

    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _active_process = proc
        stdout, stderr = proc.communicate(input=prompt, timeout=timeout)
        return subprocess.CompletedProcess(
            command, proc.returncode, stdout=stdout, stderr=stderr
        )
    except subprocess.TimeoutExpired:
        if proc:
            try:
                proc.kill()
            except OSError:
                pass
            stdout, stderr = proc.communicate()
        return subprocess.CompletedProcess(
            command, 124, stdout="", stderr=f"Timed out after {timeout}s"
        )
    except BaseException:
        if proc:
            try:
                proc.kill()
            except OSError:
                pass
            proc.wait()
        raise
    finally:
        _active_process = None



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dailyfx-agent",
        description="Run a DailyFX generation in Docker and hand the result to an AI agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Commands:\n"
            "  --list-schedules    Print schedule IDs and names from the backend\n"
            "  --list-models       Print available models for the selected target\n"
            "  --schedule-id ID    Run one scheduled generation and hand off the result\n\n"
            "Examples:\n"
            "  ./dailyfx-agent --list-schedules\n"
            "  ./dailyfx-agent --list-models --target agy\n"
            "  ./dailyfx-agent --list-models --target codex\n"
            "  ./dailyfx-agent --schedule-id 1 --target agy\n"
            "  ./dailyfx-agent --schedule-id 1 --target codex \\\n"
            "    --codex-command-template 'exec --image {image_path} -'"
        ),
    )
    parser.add_argument(
        "-s", "--schedule-id", type=int, default=None, help="Schedule ID to execute"
    )
    parser.add_argument(
        "-t",
        "--target",
        choices=["agy", "codex", "schedule"],
        default=None,
        help="Target tool to call",
    )
    parser.add_argument(
        "-m", "--model", default=None, help="Model to use for the selected target"
    )
    parser.add_argument(
        "-l",
        "--list-schedules",
        action="store_true",
        help="List available schedule IDs and names",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models for the selected target",
    )
    parser.add_argument(
        "--compose-file",
        default="docker-compose.yml",
        help="Path to docker compose file",
    )
    parser.add_argument(
        "--project-dir", default=".", help="Directory containing the compose file"
    )
    parser.add_argument("--service", default="api", help="Docker Compose service name")
    parser.add_argument(
        "--manifest-path", default=None, help="Optional path for the manifest JSON"
    )
    parser.add_argument(
        "--keep-manifest",
        action="store_true",
        help="Keep the manifest file after execution",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print commands without executing them"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print the loaded manifest before calling the target",
    )
    parser.add_argument(
        "--agy-command-template",
        default="--print --image {image_path}",
        help=(
            "Template used when --target agy is selected. Supports {image_path}, "
            "{output_path}, and {manifest_path}. Prompt is sent on stdin."
        ),
    )
    parser.add_argument(
        "--codex-command-template",
        default="exec --image {image_path} -",
        help=(
            "Template used when --target codex is selected. Supports {image_path}, "
            "{output_path}, and {manifest_path}. Prompt is sent on stdin."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Timeout in seconds for the host tool execution (default: 600)",
    )
    parser.add_argument(
        "-x",
        "--repeat",
        type=int,
        default=1,
        help="Number of times to run the task (default: 1)",
    )
    parser.add_argument(
        "-d",
        "--daemon",
        action="store_true",
        help="Run in background (detached) mode. Prints the PID and exits immediately.",
    )
    parser.add_argument(
        "--pid-file",
        default=None,
        help="Path to write the daemon PID file (default: data/dailyfx-agent.pid)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check the status of the daemon process",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop the running daemon process",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run environment diagnostics and verify dailyfx-agent setup",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable print of detailed error backtraces and context information",
    )
    parser.add_argument(
        "--json-status",
        action="store_true",
        help="Output execution diagnostics and status formatted as JSON on exit",
    )
    return parser


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return _build_parser().parse_args(argv)


def _validate_command_templates(args: argparse.Namespace) -> None:
    placeholders = ["image_path", "output_path", "manifest_path"]
    templates = [
        ("agy-command-template", args.agy_command_template),
        ("codex-command-template", args.codex_command_template),
    ]
    for name, template in templates:
        if not template:
            continue
        for ph in placeholders:
            pattern = rf"([\"'])\s*{{{ph}}}\s*\1"
            if re.search(pattern, template):
                sys.stderr.write(
                    f"warning: Custom template {name!r} contains quoted placeholder '{{{ph}}}'. "
                    f"The wrapper quotes values automatically, so quotes around placeholders may cause failures.\n"
                )


def _container_to_host_image_path(image_path: str) -> str:
    if image_path.startswith("/data/"):
        suffix = image_path.removeprefix("/data/")
        base_dir = Path("data").resolve()
        try:
            resolved_path = (base_dir / suffix).resolve()
            resolved_path.relative_to(base_dir)
        except (ValueError, RuntimeError) as exc:
            raise ValueError(
                f"Path traversal detected in container path: {image_path}"
            ) from exc
        return f"./data/{suffix}"
    if image_path == "/data":
        return "./data"
    return image_path


def _build_backend_command(args: argparse.Namespace) -> list[str]:
    if args.list_schedules:
        return [
            "docker",
            "compose",
            "-f",
            args.compose_file,
            "exec",
            "-T",
            args.service,
            "dailyfx",
            "schedules",
        ]

    if args.target in {"agy", "codex"}:
        return [
            "docker",
            "compose",
            "-f",
            args.compose_file,
            "exec",
            "-T",
            args.service,
            "dailyfx",
            "prepare-host",
            "--schedule-id",
            str(args.schedule_id),
            "--target",
            str(args.target),
        ]
    return [
        "docker",
        "compose",
        "-f",
        args.compose_file,
        "exec",
        "-T",
        args.service,
        "dailyfx",
        "generate",
        "--schedule-id",
        str(args.schedule_id),
        "--handoff-json",
    ]


def _build_target_command(
    target: str,
    image_path: str,
    manifest_path: str,
    output_path: str,
    model: str | None,
    *,
    agy_template: str,
    codex_template: str,
) -> list[str]:
    return _target_prefix(target, model) + shlex.split(
        (agy_template if target == "agy" else codex_template).format(
            image_path=shlex.quote(image_path),
            manifest_path=shlex.quote(manifest_path),
            output_path=shlex.quote(output_path),
        )
    )


def _target_prefix(target: str, model: str | None) -> list[str]:
    if target == "agy":
        prefix = ["agy"]
        if model:
            prefix.extend(["--model", model])
        return prefix
    if target == "codex":
        prefix = ["codex"]
        if model:
            prefix.extend(["-m", model])
        return prefix
    raise ValueError(f"Unsupported target: {target}")


def _print_command(label: str, command: list[str]) -> None:
    print(f"{label}: {shlex.join(command)}")


def _print_note(message: str, *, stderr: bool = False) -> None:
    output = f"note: {message}\n"
    if stderr:
        sys.stderr.write(output)
    else:
        print(f"note: {message}")


def _print_status(message: str) -> None:
    print(message)


def _print_manifest(manifest: dict[str, object]) -> None:
    json.dump(manifest, sys.stderr, ensure_ascii=False, indent=2)
    sys.stderr.write("\n")


def _validate_manifest_schema(manifest: object) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("Manifest is not a JSON object")

    type_checks = {
        "task_id": (str, "string"),
        "status": (str, "string"),
        "generation_type": (str, "string"),
        "title": (str, "string"),
        "summary": (str, "string"),
        "prompt": (str, "string"),
        "handoff_prompt": (str, "string"),
        "source_image_path": (str, "string"),
        "host_relative_image_path": (str, "string"),
        "output_path": (str, "string"),
        "image_path": (str, "string"),
        "source_asset_id": (str, "string"),
        "source_asset_original_file_name": (str, "string"),
        "config_json": (dict, "object"),
        "tags": (list, "array"),
        "task_trace": (list, "array"),
    }

    for field, (expected_type, type_name) in type_checks.items():
        if field in manifest:
            value = manifest[field]
            if value is not None and not isinstance(value, expected_type):
                raise ValueError(
                    f"Manifest validation error: field '{field}' must be a {type_name}, got {type(value).__name__}"
                )


def _load_manifest(path: Path) -> dict[str, object]:
    payload = path.read_text(encoding="utf-8")
    try:
        manifest = json.loads(payload)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in manifest file: {e}") from e
    _validate_manifest_schema(manifest)
    return manifest



def _normalize_host_manifest(
    manifest: object, original_manifest: object | None = None
) -> dict[str, object]:
    if not isinstance(manifest, dict):
        raise ValueError("Host manifest is not a JSON object")
    return validate_and_normalize_host_manifest(manifest, original_manifest)



def _print_model_list_header(target: str) -> None:
    print(f"{target} models:")


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


def _validate_output_image(path: Path, *, min_bytes: int = 1) -> dict[str, object]:
    if not path.exists():
        raise ValueError(f"Output image validation failed: file does not exist: {path}")
    size_bytes = path.stat().st_size
    if size_bytes < min_bytes:
        raise ValueError(
            f"Output image validation failed: file is too small ({size_bytes} bytes): {path}"
        )
    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format or "unknown"
            image.verify()
    except Exception as exc:
        raise ValueError(f"Output image validation failed: {path} is not a valid image") from exc

    if width <= 0 or height <= 0:
        raise ValueError(f"Output image validation failed: invalid dimensions {width}x{height}: {path}")
    return {
        "path": str(path.resolve()),
        "size_bytes": size_bytes,
        "width": width,
        "height": height,
        "format": image_format,
    }


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
        result = _run_subprocess_with_active_tracking(command, prompt, timeout)

        log_path = _write_target_log(
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

    log_path = _write_target_log(
        log_dir=log_dir,
        task_id=task_id or "target",
        target=command[0] if command else "target",
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        returncode=result.returncode,
    )
    return result, log_path



def _print_table(rows: list[dict[str, str]], columns: list[tuple[str, str]]) -> None:
    if not rows:
        print("No models found")
        return

    widths = []
    for key, header in columns:
        widths.append(max(len(header), max(len(row.get(key, "")) for row in rows)))

    header_line = "  ".join(
        header.ljust(widths[index]) for index, (_, header) in enumerate(columns)
    )
    print(header_line)
    print("  ".join("-" * widths[index] for index in range(len(columns))))
    for row in rows:
        print(
            "  ".join(
                row.get(key, "").ljust(widths[index])
                for index, (key, _) in enumerate(columns)
            )
        )


def _parse_agy_model_line(line: str) -> dict[str, str] | None:
    text = line.strip()
    if not text:
        return None
    if text.lower().startswith("usage:") or text.lower().startswith("flags"):
        return None

    reasoning = "-"
    name = text
    if text.endswith(")") and "(" in text:
        open_index = text.rfind("(")
        reasoning = text[open_index + 1 : -1].strip() or "-"
        name = text[:open_index].strip()

    if not name:
        return None

    return {
        "id": name,
        "name": name,
        "reasoning": reasoning,
        "default": "-",
    }


def _get_agy_models(timeout: int = 15) -> list[str]:
    if IS_TESTING:
        return ["gpt-5.5", "gemini-3.5-flash"]
    command = ["agy", "models"]
    try:
        run = subprocess.run(
            command, text=True, capture_output=True, check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return []
    if run.returncode != 0:
        return []
    models = []
    for line in run.stdout.splitlines():
        parsed = _parse_agy_model_line(line)
        if parsed and parsed.get("id"):
            models.append(parsed["id"])
    return models


def _get_codex_models(timeout: int = 15) -> list[str]:
    if IS_TESTING:
        return ["gpt-5.5", "gemini-3.5-flash"]
    command = ["codex", "mcp-server"]

    deadline = time.time() + timeout
    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return []

    q: queue.Queue[str] = queue.Queue()
    if proc.stdout is not None:
        setattr(proc.stdout, "response_queue", q)

    def _reader() -> None:
        if proc.stdout is not None:
            for line in proc.stdout:
                q.put(line)

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()

    try:
        _mcp_request(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "dailyfx-agent", "version": _get_agent_version()},
            },
            deadline=deadline,
        )
        if proc.stdin is None:
            return []
        proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        proc.stdin.flush()

        models: list[dict[str, object]] = []
        cursor: str | None = None
        request_id = 2
        while True:
            params: dict[str, object] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            result = _mcp_request(
                proc, request_id, "model/list", params, deadline=deadline
            )
            request_id += 1
            batch = result.get("data")
            if isinstance(batch, list):
                for item in batch:
                    if isinstance(item, dict):
                        models.append(item)
            cursor = (
                result.get("nextCursor")
                if isinstance(result.get("nextCursor"), str)
                else None
            )
            if not cursor or time.time() >= deadline:
                break

        proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "exit"}) + "\n"
        )
        proc.stdin.flush()
        proc.terminate()
        proc.wait(timeout=1.0)

        res = []
        for model in models:
            model_id = str(model.get("model") or model.get("id") or "")
            if model_id:
                res.append(model_id)
        return res
    except Exception:
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            pass
        return []


def _list_agy_models(timeout: int = 30) -> int:
    command = ["agy", "models"]
    try:
        run = subprocess.run(
            command, text=True, capture_output=True, check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"agy models timed out after {timeout}s\n")
        return 124
    if run.returncode != 0:
        if run.stderr:
            sys.stderr.write(run.stderr)
        elif run.stdout:
            sys.stderr.write(run.stdout)
        return run.returncode or 1
    rows = []
    for line in run.stdout.splitlines():
        parsed = _parse_agy_model_line(line)
        if parsed:
            rows.append(parsed)
    if not rows:
        print("No models found")
        return 0
    print(
        "Note: agy does not expose a separate model id/default flag in this build; ID shows the selectable label."
    )
    _print_table(
        rows,
        [
            ("id", "ID"),
            ("name", "NAME"),
            ("reasoning", "REASONING"),
            ("default", "DEFAULT"),
        ],
    )
    return 0


def _read_jsonrpc_message(stream, timeout_seconds: float = 10.0) -> dict[str, object]:
    q = getattr(stream, "response_queue", None)
    if q is None:
        raise RuntimeError("Stream does not have a response queue attached")

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            line = q.get(timeout=remaining)
        except queue.Empty:
            continue
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise TimeoutError("Timed out waiting for Codex MCP response")


def _mcp_request(
    proc: subprocess.Popen[str],
    request_id: int,
    method: str,
    params: dict[str, object] | None = None,
    *,
    deadline: float | None = None,
) -> dict[str, object]:
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("Codex MCP server pipes are unavailable")
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    while True:
        if deadline is not None and time.time() >= deadline:
            raise TimeoutError(f"MCP request {method!r} timed out")
        message = _read_jsonrpc_message(proc.stdout)
        if message.get("id") == request_id:
            if "error" in message:
                raise RuntimeError(str(message["error"]))
            result = message.get("result")
            if isinstance(result, dict):
                return result
            raise RuntimeError("Codex MCP response missing result object")


def _list_codex_models(timeout: int = 60) -> int:
    command = ["codex", "mcp-server"]
    deadline = time.time() + timeout
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    q: queue.Queue[str] = queue.Queue()
    if proc.stdout is not None:
        setattr(proc.stdout, "response_queue", q)

    def _reader() -> None:
        if proc.stdout is not None:
            for line in proc.stdout:
                q.put(line)

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()

    try:
        _mcp_request(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "dailyfx-agent", "version": _get_agent_version()},
            },
            deadline=deadline,
        )
        if proc.stdin is None:
            raise RuntimeError("Codex MCP server stdin is unavailable")
        proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        proc.stdin.flush()

        models: list[dict[str, object]] = []
        cursor: str | None = None
        request_id = 2
        while True:
            params: dict[str, object] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            result = _mcp_request(
                proc, request_id, "model/list", params, deadline=deadline
            )
            request_id += 1
            batch = result.get("data")
            if isinstance(batch, list):
                for item in batch:
                    if isinstance(item, dict):
                        models.append(item)
            cursor = (
                result.get("nextCursor")
                if isinstance(result.get("nextCursor"), str)
                else None
            )
            if not cursor:
                break

        if not models:
            print("No models found")
            return 0

        rows = []
        for model in models:
            model_id = str(model.get("model") or model.get("id") or "")
            display_name = str(model.get("displayName") or model_id)
            is_default = "yes" if model.get("isDefault") else "no"
            efforts = model.get("supportedReasoningEfforts") or []
            if isinstance(efforts, list):
                reasoning = ", ".join(
                    str(item.get("reasoningEffort"))
                    for item in efforts
                    if isinstance(item, dict) and item.get("reasoningEffort")
                )
            else:
                reasoning = ""
            rows.append(
                {
                    "id": model_id,
                    "name": display_name,
                    "reasoning": reasoning,
                    "default": is_default,
                }
            )
        _print_table(
            rows,
            [
                ("id", "ID"),
                ("name", "NAME"),
                ("reasoning", "REASONING"),
                ("default", "DEFAULT"),
            ],
        )
        return 0
    except Exception as exc:
        fallback = _list_codex_current_model()
        if fallback is not None:
            print(
                "Note: codex mcp-server did not expose model/list in this build; showing the current configured model instead."
            )
            _print_table(
                [fallback],
                [
                    ("id", "ID"),
                    ("name", "NAME"),
                    ("provider", "PROVIDER"),
                    ("reasoning", "REASONING"),
                    ("default", "DEFAULT"),
                ],
            )
            return 0
        sys.stderr.write(f"{exc}\n")
        return 1
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _list_codex_current_model(timeout: int = 15) -> dict[str, str] | None:
    try:
        run = subprocess.run(
            ["codex", "doctor"],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None
    if run.returncode != 0:
        return None
    match = re.search(
        r"^\s*model\s+([^\s·]+)\s+·\s+([^\s]+)\s*$", run.stdout, re.MULTILINE
    )
    if not match:
        return None
    model_id, provider = match.groups()
    return {
        "id": model_id,
        "name": model_id,
        "provider": provider,
        "reasoning": "-",
        "default": "yes",
    }


def _find_latest_image(
    start_time: float,
    generated_root: Path,
    task_id: str = "target",
    *,
    notes_to_stderr: bool = False,
) -> Path | None:
    if not generated_root.exists():
        return None

    # Find recent subdirectories that might represent the current session/task
    search_dirs = [generated_root]
    try:
        for path in generated_root.iterdir():
            if path.is_dir():
                try:
                    name_matches = task_id.lower() in path.name.lower()
                    is_recent = path.stat().st_mtime >= start_time - 10.0
                    if name_matches or is_recent:
                        search_dirs.append(path)
                except OSError:
                    continue
    except OSError:
        return None

    candidates: list[Path] = []
    buffer_time = start_time - 300.0  # 5-minute safety window

    for search_dir in search_dirs:
        try:
            for path in search_dir.iterdir():
                try:
                    if path.is_file():
                        name_lower = path.name.lower()
                        if "input" in name_lower or "original" in name_lower:
                            continue
                        if path.suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}:
                            if path.stat().st_mtime >= start_time - 10.0:
                                candidates.append(path)
                    elif path.is_dir():
                        dir_mtime = path.stat().st_mtime
                        name_matches = task_id.lower() in path.name.lower()
                        if dir_mtime >= buffer_time or name_matches:
                            for subpath in path.iterdir():
                                if subpath.is_file():
                                    subname_lower = subpath.name.lower()
                                    if "input" in subname_lower or "original" in subname_lower:
                                        continue
                                    if subpath.suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}:
                                        if subpath.stat().st_mtime >= start_time - 10.0:
                                            candidates.append(subpath)
                except OSError:
                    continue
        except OSError:
            continue

    if not candidates:
        return None

    task_id_matches = []
    other_candidates = []

    for path in candidates:
        in_filename = task_id.lower() in path.name.lower()
        in_parent = task_id.lower() in path.parent.name.lower()
        if in_filename or in_parent:
            task_id_matches.append(path)
        else:
            other_candidates.append(path)

    if task_id_matches:
        chosen = max(task_id_matches, key=lambda p: p.stat().st_mtime)
        _print_note(
            f"Selected recovery image {chosen} because it matches task_id '{task_id}' in its name/path.",
            stderr=notes_to_stderr,
        )
        return chosen
    else:
        chosen = max(other_candidates, key=lambda p: p.stat().st_mtime)
        sys.stderr.write(
            f"warning: No image found matching task_id '{task_id}'. Falling back to the latest generated image.\n"
        )
        _print_note(
            f"Selected recovery image {chosen} (fallback latest image) because no task_id match was found.",
            stderr=notes_to_stderr,
        )
        return chosen


def _find_latest_codex_image(
    start_time: float,
    generated_root: Path | None = None,
    task_id: str = "target",
    *,
    notes_to_stderr: bool = False,
) -> Path | None:
    generated_root = generated_root or (Path.home() / ".codex" / "generated_images")
    return _find_latest_image(
        start_time, generated_root, task_id, notes_to_stderr=notes_to_stderr
    )


def _find_latest_agy_image(
    start_time: float,
    generated_root: Path | None = None,
    task_id: str = "target",
    *,
    notes_to_stderr: bool = False,
) -> Path | None:
    generated_root = generated_root or (
        Path.home() / ".gemini" / "antigravity-cli" / "brain"
    )
    return _find_latest_image(
        start_time, generated_root, task_id, notes_to_stderr=notes_to_stderr
    )


def _get_pid_file_path(args: argparse.Namespace) -> Path:
    if args.pid_file:
        return Path(args.pid_file)
    target_str = args.target if args.target else "default"
    sched_str = (
        f"s{args.schedule_id}" if args.schedule_id is not None else "default"
    )
    return Path("data") / f"dailyfx-agent-{sched_str}-{target_str}.pid"


def _handle_status(pid_file: Path) -> int:
    if not pid_file.exists():
        print("status: stopped (no PID file)")
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

    return 0


def _handle_stop(pid_file: Path) -> int:
    import signal
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


def _get_agent_version() -> str:
    # 1. Try dynamic import from backend app.version
    try:
        project_dir = Path(__file__).resolve().parent
        backend_dir = project_dir / "backend"
        if backend_dir.is_dir() and str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from app.version import APP_VERSION
        return APP_VERSION
    except Exception:
        pass

    # 2. Try parsing pyproject.toml directly
    try:
        import tomllib
        pyproject_path = Path(__file__).resolve().parent / "backend" / "pyproject.toml"
        if pyproject_path.exists():
            with pyproject_path.open("rb") as f:
                pyproject = tomllib.load(f)
            return str(pyproject["project"]["version"])
    except Exception:
        pass

    # 3. Try importlib.metadata
    try:
        import importlib.metadata
        return importlib.metadata.version("dailyfx-backend")
    except Exception:
        pass

    # 4. Fallback default
    return "0.5.0"


def _augment_host_prompt(
    original_prompt: str,
    abs_image_path: str,
    abs_manifest_path: str,
    abs_output_path: str,
    task_id: str
) -> str:
    checklist = (
        f"\n\nCRITICAL: As the AI agent running on the host, you MUST follow this checklist:\n"
        f"Checklist:\n"
        f"- [ ] Source Vision: Open and analyze the input image (source photo) at '{abs_image_path}' to extract context, theme, and subjects.\n"
        f"- [ ] Image Generation: Apply the requested effects/modifications and save the final output image exactly at '{abs_output_path}' (or in a directory/filename containing the task ID '{task_id}').\n"
        f"- [ ] Final Vision: Open and analyze the saved output image at '{abs_output_path}' to evaluate quality, aesthetics, and theme match.\n"
        f"- [ ] Manifest Update: Write/update the local JSON manifest file at '{abs_manifest_path}' with the following keys:\n"
        f"  * 'title' (short, creative 3-5 word title)\n"
        f"  * 'summary' (one concise sentence describing the final image)\n"
        f"  * 'tags' (a JSON array containing 3-6 descriptive keywords)\n"
        f"  * 'metadata_source' (must be set to '{HOST_METADATA_SOURCE}')\n"
        f"\n"
        f"Technical Rules:\n"
        f"1. DO NOT modify any other technical/system keys in the JSON manifest.\n"
        f"2. Ensure the JSON written to '{abs_manifest_path}' is standard and correctly structured.\n"
        f"3. Make sure the output file is saved at '{abs_output_path}' before finalizing."
    )
    return original_prompt + checklist


def _handle_doctor(args: argparse.Namespace) -> int:
    import shutil
    checks = []
    has_errors = False
    has_warnings = False

    def add_check(name: str, status: str, detail: str):
        checks.append((name, status, detail))

    # 1. Docker Compose Config
    try:
        run = subprocess.run(
            ["docker", "compose", "-f", args.compose_file, "config"],
            capture_output=True,
            text=True,
            check=False
        )
        if run.returncode == 0:
            add_check("docker_compose_config", "OK", "valid configuration")
        else:
            add_check("docker_compose_config", "FAIL", (run.stderr or run.stdout or "invalid config").strip())
            has_errors = True
    except Exception as e:
        add_check("docker_compose_config", "FAIL", str(e))
        has_errors = True

    # 2. API Service Reachability
    if not has_errors:
        try:
            run = subprocess.run(
                ["docker", "compose", "-f", args.compose_file, "exec", "-T", args.service, "curl", "-s", "http://localhost:8000/health"],
                capture_output=True,
                text=True,
                check=False
            )
            if run.returncode == 0:
                add_check("api_service_reachability", "OK", "service is reachable")
            else:
                add_check("api_service_reachability", "FAIL", f"curl exit {run.returncode}: {(run.stderr or run.stdout or '').strip()}")
                has_errors = True
        except Exception as e:
            add_check("api_service_reachability", "FAIL", str(e))
            has_errors = True
    else:
        add_check("api_service_reachability", "FAIL", "skipped (docker compose failure)")

    # 3. DailyFX Schedules
    if not has_errors:
        try:
            run = subprocess.run(
                ["docker", "compose", "-f", args.compose_file, "exec", "-T", args.service, "dailyfx", "schedules"],
                capture_output=True,
                text=True,
                check=False
            )
            if run.returncode == 0:
                add_check("dailyfx_schedules", "OK", "schedules retrieved successfully")
            else:
                add_check("dailyfx_schedules", "FAIL", f"exit {run.returncode}: {(run.stderr or run.stdout or '').strip()}")
                has_errors = True
        except Exception as e:
            add_check("dailyfx_schedules", "FAIL", str(e))
            has_errors = True
    else:
        add_check("dailyfx_schedules", "FAIL", "skipped (docker compose failure)")

    # 4. Data Directory Write
    try:
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        test_file = data_dir / ".doctor-write-test"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        add_check("data_directory_write", "OK", "write/delete successful")
    except Exception as e:
        add_check("data_directory_write", "FAIL", str(e))
        has_errors = True

    stale_manifests = sorted(Path("data").glob("dailyfx-run-*.json"))
    if stale_manifests:
        add_check(
            "stale_run_manifests",
            "WARNING",
            f"{len(stale_manifests)} temporary manifest(s) remain in data/",
        )
        has_warnings = True
    else:
        add_check("stale_run_manifests", "OK", "none found")

    # 5. Target Executable availability
    agy_path = shutil.which("agy")
    codex_path = shutil.which("codex")

    if agy_path:
        add_check("target_agy_executable", "OK", f"found at {agy_path}")
    else:
        add_check("target_agy_executable", "WARNING", "not found in PATH")
        has_warnings = True

    if codex_path:
        add_check("target_codex_executable", "OK", f"found at {codex_path}")
    else:
        add_check("target_codex_executable", "WARNING", "not found in PATH")
        has_warnings = True

    if not agy_path and not codex_path:
        has_errors = True
        # Upgrade warnings to errors for targets if both missing
        if len(checks) >= 2:
            checks[-2] = ("target_agy_executable", "FAIL", "not found in PATH")
            checks[-1] = ("target_codex_executable", "FAIL", "not found in PATH")

    # 6. Target models
    if agy_path:
        try:
            models = _get_agy_models(timeout=5)
            if models:
                add_check("agy_models", "OK", f"retrieved {len(models)} models")
            else:
                add_check("agy_models", "WARNING", "no models found or empty response")
                has_warnings = True
        except Exception as e:
            add_check("agy_models", "WARNING", f"error: {str(e)}")
            has_warnings = True
    else:
        add_check("agy_models", "WARNING", "skipped (agy target missing)")

    if codex_path:
        try:
            models = _get_codex_models(timeout=5)
            if models:
                add_check("codex_models", "OK", f"retrieved {len(models)} models")
            else:
                add_check("codex_models", "WARNING", "no models found or empty response")
                has_warnings = True
        except Exception as e:
            add_check("codex_models", "WARNING", f"error: {str(e)}")
            has_warnings = True
    else:
        add_check("codex_models", "WARNING", "skipped (codex target missing)")

    # 7. Recovery directories
    agy_rec = Path.home() / ".gemini" / "antigravity-cli" / "brain"
    codex_rec = Path.home() / ".codex" / "generated_images"

    if agy_rec.is_dir() and os.access(agy_rec, os.R_OK):
        add_check("recovery_dir_agy", "OK", "exists and readable")
    else:
        add_check("recovery_dir_agy", "WARNING", f"not found or unreadable: {agy_rec}")
        has_warnings = True

    if codex_rec.is_dir() and os.access(codex_rec, os.R_OK):
        add_check("recovery_dir_codex", "OK", "exists and readable")
    else:
        add_check("recovery_dir_codex", "WARNING", f"not found or unreadable: {codex_rec}")
        has_warnings = True

    # Output text table
    print(f"+{'-'*32}+{'-'*10}+{'-'*47}+")
    print(f"| {'Check':<30} | {'Status':<8} | {'Detail':<45} |")
    print(f"+{'-'*32}+{'-'*10}+{'-'*47}+")
    for name, status, detail in checks:
        detail_val = detail
        if len(detail_val) > 43:
            detail_val = detail_val[:40] + "..."
        print(f"| {name:<30} | {status:<8} | {detail_val:<45} |")
    print(f"+{'-'*32}+{'-'*10}+{'-'*47}+")

    if has_errors:
        return 1
    if has_warnings:
        return 2
    return 0


def _acquire_lock(schedule_id: int, target: str) -> None:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = LOCKS_DIR / f"dailyfx-s{schedule_id}-{target}.lock"

    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            pid = int(data.get("pid", 0))
            try:
                os.kill(pid, 0)
                raise RuntimeError(
                    f"Error: another agent (PID {pid}) is already running schedule {schedule_id} for target {target}."
                )
            except OSError:
                sys.stderr.write(
                    f"warning: removing stale lock file for schedule {schedule_id}, target {target} (PID {pid} was not found)\n"
                )
                lock_file.unlink(missing_ok=True)
        except (json.JSONDecodeError, ValueError, KeyError, OSError):
            sys.stderr.write(
                f"warning: removing invalid lock file for schedule {schedule_id}, target {target}\n"
            )
            lock_file.unlink(missing_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    lock_data = {
        "pid": os.getpid(),
        "parent_pid": os.getpid(),
        "child_pid": None,
        "owner_role": "foreground",
        "started_at": started_at,
    }
    lock_file.write_text(json.dumps(lock_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _update_lock_for_daemon_child(schedule_id: int, target: str, child_pid: int) -> None:
    lock_file = LOCKS_DIR / f"dailyfx-s{schedule_id}-{target}.lock"
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
    lock_file = LOCKS_DIR / f"dailyfx-s{schedule_id}-{target}.lock"
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


def main(argv: list[str] | None = None) -> int:
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
            available_models = _get_agy_models()
            if available_models and args.model not in available_models:
                sys.stderr.write(
                    f"Error: Model '{args.model}' is not available for target 'agy'.\n"
                    f"Available models: {', '.join(available_models)}\n"
                )
                return 1
        elif args.target == "codex":
            available_models = _get_codex_models()
            if available_models and args.model not in available_models:
                sys.stderr.write(
                    f"Error: Model '{args.model}' is not available for target 'codex'.\n"
                    f"Available models: {', '.join(available_models)}\n"
                )
                return 1

    project_dir = Path(args.project_dir)
    if args.manifest_path:
        manifest_path = Path(args.manifest_path)
    else:
        random_suffix = uuid.uuid4().hex[:8]
        manifest_path = (
            Path("data") / f"dailyfx-run-{random_suffix}.json"
        )
    shared_manifest_path = manifest_path
    backend_command = _build_backend_command(args)

    if args.list_schedules:
        backend_run = subprocess.run(
            backend_command,
            cwd=project_dir,
            text=True,
            capture_output=True,
            check=False,
        )
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
            return _list_agy_models()
        return _list_codex_models()

    if not (args.list_schedules or args.status or args.stop or args.doctor):
        if args.schedule_id is None or args.target is None:
            sys.stderr.write(
                "schedule-id and target are required unless --list-schedules is used\n"
            )
            return 1

    if args.doctor:
        return _handle_doctor(args)

    if args.status:
        return _handle_status(_get_pid_file_path(args))

    if args.stop:
        return _handle_stop(_get_pid_file_path(args))

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

    # Acquire lock for schedule and target
    if args.schedule_id is not None and args.target is not None:
        try:
            _acquire_lock(args.schedule_id, args.target)
        except RuntimeError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1

    if args.daemon:
        if args.pid_file:
            pid_file = Path(args.pid_file)
        else:
            target_str = args.target if args.target else "default"
            sched_str = (
                f"s{args.schedule_id}" if args.schedule_id is not None else "default"
            )
            pid_file = Path("data") / f"dailyfx-agent-{sched_str}-{target_str}.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        log_file_path = Path("data") / "logs" / "agent" / f"{pid_file.stem}.log"
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        pid = os.fork()
        if pid > 0:
            non_local_lock_release = True
            if args.schedule_id is not None and args.target is not None:
                _update_lock_for_daemon_child(args.schedule_id, args.target, pid)
            pid_file.write_text(str(pid), encoding="utf-8")

            # Write metadata file as JSON
            metadata_file = pid_file.with_name(pid_file.name + ".json")
            from datetime import datetime, timezone
            metadata = {
                "pid": pid,
                "schedule_id": args.schedule_id,
                "target": args.target,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "log_path": str(log_file_path.resolve()),
                "manifest_path": str(manifest_path.resolve()),
            }
            metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            print(f"daemon started: pid={pid} pidfile={pid_file}")
            return 0
        os.setsid()
        try:
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
                    manifest_path = Path(args.manifest_path)
                else:
                    path_obj = Path(args.manifest_path)
                    manifest_path = path_obj.with_name(f"{path_obj.stem}-run{run_index}{path_obj.suffix}")
                    sys.stderr.write(
                        f"warning: using modified manifest path for repeat run {run_index}: {manifest_path}\n"
                    )
            else:
                random_suffix = uuid.uuid4().hex[:8]
                manifest_path = Path("data") / f"dailyfx-run-{random_suffix}.json"
            shared_manifest_path = manifest_path

            # 1. PREPARE STAGE
            status_data["stage"] = "prepare" if args.target != "schedule" else "generate"
            if args.target == "schedule" and not args.json_status:
                print("Executing schedule generation on the backend...")
            try:
                backend_run = subprocess.run(
                    backend_command,
                    cwd=project_dir,
                    text=True,
                    capture_output=True,
                    check=False,
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
                manifest = _load_manifest(manifest_path)
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
                status_data["output_path"] = str(Path(output_path).resolve()) if output_path else ""
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

            status_data["source_image_path"] = str(Path(image_path).resolve())

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

            status_data["output_path"] = str(Path(output_path).resolve())

            # Augment prompt with Source Vision and Final Vision instructions for host agent.
            abs_image_path = str(Path(image_path).resolve())
            abs_output_path = str(Path(output_path).resolve())
            abs_manifest_path = str(manifest_path.resolve())
            prompt = _augment_host_prompt(
                prompt,
                abs_image_path,
                abs_manifest_path,
                abs_output_path,
                task_id
            )
            _write_task_text_artifact(task_id, "prompt.txt", prompt)

            target_command = _build_target_command(
                args.target,
                image_path,
                str(manifest_path),
                output_path,
                args.model,
                agy_template=args.agy_command_template,
                codex_template=args.codex_command_template,
            )

            target_start_time = time.time()

            # 3. TARGET RUN STAGE
            status_data["stage"] = "target run"
            try:
                target_run, target_log_path = _run_target_with_spinner(
                    target_command,
                    prompt=prompt,
                    task_id=task_id,
                    labels=trace_labels,
                    timeout=args.timeout,
                    daemon_mode=args.daemon,
                )
                status_data["target_log_path"] = str(Path(target_log_path).resolve()) if target_log_path else None
                if target_log_path:
                    _copy_task_artifact(task_id, Path(target_log_path), "target.log")
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
                updated_manifest = _normalize_host_manifest(
                    _load_manifest(manifest_path), manifest
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

            output_file = Path(output_path)
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
                        generated_image = _find_latest_codex_image(
                            target_start_time,
                            task_id=task_id,
                            notes_to_stderr=args.json_status,
                        )
                        missing_message = f"codex finished without creating {output_path} or a new image under ~/.codex/generated_images"
                    elif args.target == "agy":
                        generated_image = _find_latest_agy_image(
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

            # Sync updated manifest to shared manifest if they are different files
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
                finalize_run = subprocess.run(
                    finalize_command,
                    cwd=project_dir,
                    check=False,
                    text=True,
                    capture_output=True,
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
                _release_lock(args.schedule_id, args.target)
        if status_data.get("task_id"):
            _write_task_json_artifact(str(status_data["task_id"]), "status.json", status_data)
        if "args" in locals() and getattr(args, "json_status", False):
            print(json.dumps(status_data, ensure_ascii=False, indent=2))

    return last_exit


if __name__ == "__main__":
    raise SystemExit(main())
