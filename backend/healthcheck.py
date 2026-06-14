#!/usr/bin/env python3
import json
import sys
import time
import urllib.request
from pathlib import Path

from app.config import get_settings


def check_health():
    try:
        settings = get_settings()
        port = settings.app_port
        data_dir = settings.data_dir
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)

    url = f"http://localhost:{port}/api/health"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                print(f"API health check failed with status code {response.status}", file=sys.stderr)
                sys.exit(1)

            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") != "ok":
                print(f"API health status is not ok: {data}", file=sys.stderr)
                sys.exit(1)
    except Exception as e:
        print(f"Error connecting to health API {url}: {e}", file=sys.stderr)
        sys.exit(1)

    scheduler_health_path = Path(data_dir) / "scheduler.health"
    if not scheduler_health_path.exists():
        print(f"Scheduler health file does not exist: {scheduler_health_path}", file=sys.stderr)
        sys.exit(1)

    try:
        age_seconds = time.time() - scheduler_health_path.stat().st_mtime
        if age_seconds > 120:
            print(f"Scheduler heartbeat is stale: {age_seconds:.1f}s old (limit 120s)", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error checking scheduler health file: {e}", file=sys.stderr)
        sys.exit(1)

    print("Health check passed.")
    sys.exit(0)


if __name__ == "__main__":
    check_health()
