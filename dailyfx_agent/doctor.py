from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dailyfx_agent.config import (
    _DOCKER_COMPOSE_CONFIG_TIMEOUT,
    _DOCKER_COMPOSE_HEALTH_TIMEOUT,
    _DOCKER_COMPOSE_SCHEDULES_TIMEOUT,
    _DOCTOR_HTTP_PROBE_TIMEOUT,
)
from dailyfx_agent.models import _get_agy_models, _get_codex_models


def _handle_clean_manifests() -> int:
    stale_manifests = list(Path("data").glob("dailyfx-run-*.json"))
    if not stale_manifests:
        print("No stale temporary manifests found in data/.")
        return 0

    count = 0
    for path in stale_manifests:
        try:
            path.unlink(missing_ok=True)
            count += 1
        except Exception as e:
            sys.stderr.write(f"Failed to remove {path.name}: {e}\n")

    print(f"Successfully removed {count} stale manifest file(s) from data/.")
    return 0


def _handle_doctor(args: argparse.Namespace) -> int:
    checks = []
    has_errors = False
    has_warnings = False

    def add_check(name: str, status: str, detail: str):
        checks.append((name, status, detail))

    def replace_check(name: str, status: str, detail: str) -> None:
        for index, (check_name, _, _) in enumerate(checks):
            if check_name == name:
                checks[index] = (name, status, detail)
                return

    # 1. Docker Compose Config
    try:
        run = subprocess.run(
            ["docker", "compose", "-f", args.compose_file, "config"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_DOCKER_COMPOSE_CONFIG_TIMEOUT,
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
                ["docker", "compose", "-f", args.compose_file, "exec", "-T", args.service, "python", "-c", f"import urllib.request; urllib.request.urlopen('http://localhost:8438/api/health', timeout={_DOCTOR_HTTP_PROBE_TIMEOUT})"],
                capture_output=True,
                text=True,
                check=False,
                timeout=_DOCKER_COMPOSE_HEALTH_TIMEOUT,
            )
            if run.returncode == 0:
                add_check("api_service_reachability", "OK", "service is reachable")
            else:
                add_check("api_service_reachability", "FAIL", f"check exit {run.returncode}: {(run.stderr or run.stdout or '').strip()}")
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
                check=False,
                timeout=_DOCKER_COMPOSE_SCHEDULES_TIMEOUT,
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
        replace_check("target_agy_executable", "FAIL", "not found in PATH")
        replace_check("target_codex_executable", "FAIL", "not found in PATH")

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
