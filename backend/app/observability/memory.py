from __future__ import annotations

import os
from pathlib import Path

_CGROUP_ROOT = Path("/sys/fs/cgroup")


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def process_rss_bytes() -> int | None:
    """Return the current resident memory of this Linux process."""
    try:
        resident_pages = int((Path("/proc/self/statm").read_text(encoding="utf-8").split())[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, IndexError, ValueError):
        return None


def cgroup_memory_bytes() -> dict[str, int]:
    """Return available cgroup v2 memory counters without failing outside Docker."""
    counters = {
        "cgroup_current_bytes": _read_int(_CGROUP_ROOT / "memory.current"),
        "cgroup_peak_bytes": _read_int(_CGROUP_ROOT / "memory.peak"),
    }
    return {name: value for name, value in counters.items() if value is not None}


def cgroup_memory_events() -> dict[str, int]:
    try:
        raw_events = (_CGROUP_ROOT / "memory.events").read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    events: dict[str, int] = {}
    for line in raw_events:
        key, _, raw_value = line.partition(" ")
        if key in {"oom", "oom_kill"}:
            try:
                events[f"cgroup_memory_{key}_total"] = int(raw_value)
            except ValueError:
                continue
    return events


def memory_snapshot() -> dict[str, int]:
    """Capture memory counters suitable for stage traces and metrics."""
    snapshot = cgroup_memory_bytes()
    rss = process_rss_bytes()
    if rss is not None:
        snapshot["process_rss_bytes"] = rss
    return snapshot
