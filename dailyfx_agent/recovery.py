from __future__ import annotations

import sys
from pathlib import Path

from dailyfx_agent.config import (
    _RECOVERY_DIR_BUFFER_SECONDS,
    _RECOVERY_FILE_BUFFER_SECONDS,
)
from dailyfx_agent.utils import _print_note


def _find_latest_image(
    start_time: float,
    generated_root: Path,
    task_id: str = "target",
    *,
    notes_to_stderr: bool = False,
    strict: bool = True,
) -> Path | None:
    if not generated_root.exists():
        return None

    search_dirs = [generated_root]
    try:
        for path in generated_root.iterdir():
            if path.is_dir():
                try:
                    name_matches = task_id.lower() in path.name.lower()
                    is_recent = path.stat().st_mtime >= start_time - _RECOVERY_DIR_BUFFER_SECONDS
                    if name_matches or is_recent:
                        search_dirs.append(path)
                except OSError:
                    continue
    except OSError:
        return None

    candidates: list[Path] = []
    dir_cutoff = start_time - _RECOVERY_DIR_BUFFER_SECONDS
    file_cutoff = start_time - _RECOVERY_FILE_BUFFER_SECONDS

    for search_dir in search_dirs:
        try:
            for path in search_dir.iterdir():
                try:
                    if path.is_file():
                        name_lower = path.name.lower()
                        if "input" in name_lower or "original" in name_lower:
                            continue
                        if path.suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}:
                            if path.stat().st_mtime >= file_cutoff:
                                candidates.append(path)
                    elif path.is_dir():
                        dir_mtime = path.stat().st_mtime
                        name_matches = task_id.lower() in path.name.lower()
                        if dir_mtime >= dir_cutoff or name_matches:
                            for subpath in path.iterdir():
                                if subpath.is_file():
                                    subname_lower = subpath.name.lower()
                                    if "input" in subname_lower or "original" in subname_lower:
                                        continue
                                    if subpath.suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}:
                                        if subpath.stat().st_mtime >= file_cutoff:
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

    if strict:
        sys.stderr.write(
            f"error: No image found matching task_id '{task_id}'; refusing unmatched recovery.\n"
        )
        return None

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
    strict: bool = True,
) -> Path | None:
    generated_root = generated_root or (Path.home() / ".codex" / "generated_images")
    return _find_latest_image(
        start_time, generated_root, task_id,
        notes_to_stderr=notes_to_stderr, strict=strict,
    )


def _find_latest_agy_image(
    start_time: float,
    generated_root: Path | None = None,
    task_id: str = "target",
    *,
    notes_to_stderr: bool = False,
    strict: bool = True,
) -> Path | None:
    generated_root = generated_root or (
        Path.home() / ".gemini" / "antigravity-cli" / "brain"
    )
    return _find_latest_image(
        start_time, generated_root, task_id,
        notes_to_stderr=notes_to_stderr, strict=strict,
    )


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
