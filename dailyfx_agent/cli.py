from __future__ import annotations

import argparse
import re
import shlex
import sys


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
        default="--print {prompt}",
        help=(
            "Template used when --target agy is selected. Supports {image_path}, "
            "{output_path}, {manifest_path}, and {prompt}. Prompt is sent on stdin."
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
        help="Path to write the daemon PID file (default: data/dailyfx-agent-{target}.pid)",
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
        "--clean-manifests",
        action="store_true",
        help="Remove stale temporary manifest files (dailyfx-run-*.json) from the data/ directory",
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
    parser.add_argument("--_queue-worker", action="store_true", help=argparse.SUPPRESS)
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
    prompt: str,
    *,
    agy_template: str,
    codex_template: str,
) -> list[str]:
    return _target_prefix(target, model) + shlex.split(
        (agy_template if target == "agy" else codex_template).format(
            image_path=shlex.quote(image_path),
            manifest_path=shlex.quote(manifest_path),
            output_path=shlex.quote(output_path),
            prompt=shlex.quote(prompt),
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
