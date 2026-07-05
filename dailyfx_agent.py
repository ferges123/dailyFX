from __future__ import annotations

import argparse
import itertools
import json
import re
import select
import shlex
import subprocess
import sys
import tempfile
import time
import threading
from pathlib import Path


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
    parser.add_argument("-s", "--schedule-id", type=int, default=None, help="Schedule ID to execute")
    parser.add_argument("-t", "--target", choices=["agy", "codex"], default=None, help="Target tool to call")
    parser.add_argument("-m", "--model", default=None, help="Model to use for the selected target")
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
    parser.add_argument("--compose-file", default="docker-compose.yml", help="Path to docker compose file")
    parser.add_argument("--project-dir", default=".", help="Directory containing the compose file")
    parser.add_argument("--service", default="api", help="Docker Compose service name")
    parser.add_argument("--manifest-path", default=None, help="Optional path for the manifest JSON")
    parser.add_argument("--keep-manifest", action="store_true", help="Keep the manifest file after execution")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print the loaded manifest before calling the target")
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
    return parser


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return _build_parser().parse_args(argv)


def _container_to_host_image_path(image_path: str) -> str:
    if image_path.startswith("/data/"):
        return f"./data/{image_path.removeprefix('/data/')}"
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
        (
            agy_template if target == "agy" else codex_template
        ).format(
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


def _print_note(message: str) -> None:
    print(f"note: {message}")


def _print_status(message: str) -> None:
    print(message)


def _print_manifest(manifest: dict[str, object]) -> None:
    json.dump(manifest, sys.stderr, ensure_ascii=False, indent=2)
    sys.stderr.write("\n")


def _load_manifest(path: Path) -> dict[str, object]:
    payload = path.read_text(encoding="utf-8")
    return json.loads(payload)


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

    logs = sorted(
        (path for path in log_dir.glob("dailyfx-agent-*.log") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
    )
    for old_log in logs[:-keep]:
        old_log.unlink(missing_ok=True)


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


def _run_target_with_spinner(
    command: list[str],
    *,
    prompt: str,
    task_id: str,
    labels: list[str],
) -> tuple[subprocess.CompletedProcess[str], Path]:
    log_dir = Path(tempfile.gettempdir()) / "dailyfx-agent-logs"
    spinner_labels = (labels[:5] if labels else []) or ["waiting for image provider"]
    spinner_frames = itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
    stop_event = threading.Event()
    spinner_state = {"index": 0}

    def _spinner() -> None:
        while not stop_event.is_set():
            frame = next(spinner_frames)
            label_index = spinner_state["index"] if spinner_state["index"] < len(spinner_labels) else len(spinner_labels) - 1
            label = spinner_labels[label_index]
            sys.stderr.write(f"\r{frame} {label}   ")
            sys.stderr.flush()
            spinner_state["index"] += 1
            stop_event.wait(0.7)
        sys.stderr.write("\r")
        sys.stderr.flush()

    thread = threading.Thread(target=_spinner, daemon=True)
    thread.start()
    try:
        result = subprocess.run(command, input=prompt, text=True, capture_output=True, check=False)
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

    header_line = "  ".join(header.ljust(widths[index]) for index, (_, header) in enumerate(columns))
    print(header_line)
    print("  ".join("-" * widths[index] for index in range(len(columns))))
    for row in rows:
        print("  ".join(row.get(key, "").ljust(widths[index]) for index, (key, _) in enumerate(columns)))


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


def _list_agy_models() -> int:
    command = ["agy", "models"]
    run = subprocess.run(command, text=True, capture_output=True, check=False)
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
    print("Note: agy does not expose a separate model id/default flag in this build; ID shows the selectable label.")
    _print_table(rows, [("id", "ID"), ("name", "NAME"), ("reasoning", "REASONING"), ("default", "DEFAULT")])
    return 0


def _read_jsonrpc_message(stream, timeout_seconds: float = 10.0) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        remaining = max(0.0, deadline - time.time())
        readable, _, _ = select.select([stream], [], [], remaining)
        if not readable:
            continue
        line = stream.readline()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise TimeoutError("Timed out waiting for Codex MCP response")


def _mcp_request(proc: subprocess.Popen[str], request_id: int, method: str, params: dict[str, object] | None = None) -> dict[str, object]:
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("Codex MCP server pipes are unavailable")
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    while True:
        message = _read_jsonrpc_message(proc.stdout)
        if message.get("id") == request_id:
            if "error" in message:
                raise RuntimeError(str(message["error"]))
            result = message.get("result")
            if isinstance(result, dict):
                return result
            raise RuntimeError("Codex MCP response missing result object")


def _list_codex_models() -> int:
    command = ["codex", "mcp-server"]
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _mcp_request(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "dailyfx-agent", "version": "0.3.51"},
            },
        )
        if proc.stdin is None:
            raise RuntimeError("Codex MCP server stdin is unavailable")
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()

        models: list[dict[str, object]] = []
        cursor: str | None = None
        request_id = 2
        while True:
            params: dict[str, object] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            result = _mcp_request(proc, request_id, "model/list", params)
            request_id += 1
            batch = result.get("data")
            if isinstance(batch, list):
                for item in batch:
                    if isinstance(item, dict):
                        models.append(item)
            cursor = result.get("nextCursor") if isinstance(result.get("nextCursor"), str) else None
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
        _print_table(rows, [("id", "ID"), ("name", "NAME"), ("reasoning", "REASONING"), ("default", "DEFAULT")])
        return 0
    except Exception as exc:
        fallback = _list_codex_current_model()
        if fallback is not None:
            print(
                "Note: codex mcp-server did not expose model/list in this build; showing the current configured model instead."
            )
            _print_table(
                [fallback],
                [("id", "ID"), ("name", "NAME"), ("provider", "PROVIDER"), ("reasoning", "REASONING"), ("default", "DEFAULT")],
            )
            return 0
        sys.stderr.write(f"{exc}\n")
        return 1
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


def _list_codex_current_model() -> dict[str, str] | None:
    run = subprocess.run(["codex", "doctor"], text=True, capture_output=True, check=False)
    if run.returncode != 0:
        return None
    match = re.search(r"^\s*model\s+([^\s·]+)\s+·\s+([^\s]+)\s*$", run.stdout, re.MULTILINE)
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


def _find_latest_image(start_time: float, generated_root: Path) -> Path | None:
    if not generated_root.exists():
        return None

    candidates: list[Path] = []
    for path in generated_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".png", ".webp", ".jpg", ".jpeg"}:
            continue
        try:
            if path.stat().st_mtime >= start_time:
                candidates.append(path)
        except OSError:
            continue

    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _find_latest_codex_image(start_time: float, generated_root: Path | None = None) -> Path | None:
    generated_root = generated_root or (Path.home() / ".codex" / "generated_images")
    return _find_latest_image(start_time, generated_root)


def _find_latest_agy_image(start_time: float, generated_root: Path | None = None) -> Path | None:
    generated_root = generated_root or (Path.home() / ".gemini" / "antigravity-cli" / "brain")
    return _find_latest_image(start_time, generated_root)


def main(argv: list[str] | None = None) -> int:
    effective_argv = sys.argv[1:] if argv is None else argv
    if len(effective_argv) == 0:
        _build_parser().print_help()
        return 0

    args = _parse_args(effective_argv)
    project_dir = Path(args.project_dir)
    manifest_path = Path(args.manifest_path) if args.manifest_path else Path(tempfile.gettempdir()) / "dailyfx-run.json"
    shared_manifest_path = Path("data") / manifest_path.name
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
        _print_model_list_header(args.target)
        if args.target == "agy":
            return _list_agy_models()
        return _list_codex_models()

    if args.schedule_id is None or args.target is None:
        sys.stderr.write("schedule-id and target are required unless --list-schedules is used\n")
        return 1

    if args.dry_run:
        target_preview = _target_prefix(args.target, args.model)
        _print_command("backend", backend_command)
        _print_command("manifest", ["write", str(manifest_path), "and", str(shared_manifest_path)])
        _print_command(
            "target",
            target_preview
            + shlex.split(
                (
                    args.agy_command_template if args.target == "agy" else args.codex_command_template
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

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(backend_run.stdout, encoding="utf-8")
    if shared_manifest_path != manifest_path:
        shared_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        shared_manifest_path.write_text(backend_run.stdout, encoding="utf-8")
    try:
        manifest = _load_manifest(manifest_path)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"Invalid JSON from backend CLI: {exc}\n")
        return 1

    if args.verbose:
        _print_manifest(manifest)

    task_id = str(manifest.get("task_id") or "").strip() or "target"
    prompt = str(manifest.get("prompt") or manifest.get("handoff_prompt") or "").strip()
    if not prompt:
        sys.stderr.write("Backend manifest did not include prompt\n")
        return 1

    task_trace = manifest.get("task_trace")
    if not isinstance(task_trace, list):
        config_json = manifest.get("config_json")
        if isinstance(config_json, dict):
            task_trace = config_json.get("task_trace")
    trace_labels = _task_trace_labels(task_trace)
    print(f"image provider: {args.target}")

    image_path = str(manifest.get("source_image_path") or manifest.get("host_relative_image_path") or "").strip()
    if not image_path:
        image_path = _container_to_host_image_path(str(manifest.get("image_path") or ""))
    elif image_path.startswith("/data/"):
        image_path = _container_to_host_image_path(image_path)
    if not image_path:
        sys.stderr.write("Backend manifest did not include source_image_path\n")
        return 1

    output_path = str(manifest.get("output_path") or manifest.get("image_path") or "").strip()
    if output_path.startswith("/data/"):
        output_path = _container_to_host_image_path(output_path)
    if not output_path:
        sys.stderr.write("Backend manifest did not include output_path\n")
        return 1

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
    target_run, target_log_path = _run_target_with_spinner(
        target_command,
        prompt=prompt,
        task_id=task_id,
        labels=trace_labels,
    )
    if target_run.returncode != 0:
        if target_run.stderr:
            sys.stderr.write(target_run.stderr)
        elif target_run.stdout:
            sys.stderr.write(target_run.stdout)
        sys.stderr.write(f"\nlog saved to {target_log_path}\n")
        return target_run.returncode or 1

    output_file = Path(output_path)
    if not output_file.is_absolute():
        output_file = project_dir / output_file
    if not output_file.exists():
        generated_image = None
        missing_message = None
        if args.target == "codex":
            generated_image = _find_latest_codex_image(target_start_time)
            missing_message = (
                f"codex finished without creating {output_path} or a new image under ~/.codex/generated_images"
            )
        elif args.target == "agy":
            generated_image = _find_latest_agy_image(target_start_time)
            missing_message = (
                f"agy finished without creating {output_path} or a new image under ~/.gemini/antigravity-cli/brain"
            )

        if generated_image is not None:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_bytes(generated_image.read_bytes())
        else:
            sys.stderr.write(f"{missing_message}\n")
            return 1

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
    finalize_run = subprocess.run(finalize_command, cwd=project_dir, check=False, text=True, capture_output=True)
    if finalize_run.returncode != 0:
        if finalize_run.stderr:
            sys.stderr.write(finalize_run.stderr)
        elif finalize_run.stdout:
            sys.stderr.write(finalize_run.stdout)
        return finalize_run.returncode or 1

    if not args.keep_manifest:
        if not args.manifest_path:
            manifest_path.unlink(missing_ok=True)
        if shared_manifest_path != manifest_path:
            shared_manifest_path.unlink(missing_ok=True)

    print(f"done: {output_path}")
    if args.verbose:
        print(f"log: {target_log_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
