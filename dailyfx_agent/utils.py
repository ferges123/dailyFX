from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

_active_process: subprocess.Popen[str] | None = None
_original_subprocess_run = subprocess.run


def _atomic_write_text(path: Path, content: str, *, mode: int = 0o600) -> None:
    """Replace a small state file atomically, keeping it private."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise


def _terminate_process_gracefully(
    proc: subprocess.Popen[str], *, grace_seconds: float = 5.0
) -> None:
    """Ask a child to exit cleanly, falling back to SIGKILL after a grace period."""
    terminate = getattr(proc, "terminate", None)
    if not callable(terminate):
        proc.kill()
        return
    try:
        terminate()
    except OSError:
        return
    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            return
        proc.wait()


def _sigterm_handler(signum, frame):
    active_proc = _active_process
    if active_proc:
        try:
            _terminate_process_gracefully(active_proc)
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
                _terminate_process_gracefully(proc, grace_seconds=2.0)
            except OSError:
                pass
            stdout, stderr = proc.communicate()
        return subprocess.CompletedProcess(
            command, 124, stdout="", stderr=f"Timed out after {timeout}s"
        )
    except BaseException:
        if proc:
            try:
                _terminate_process_gracefully(proc, grace_seconds=2.0)
            except OSError:
                pass
            proc.wait()
        raise
    finally:
        _active_process = None


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


def _print_command(label: str, command: list[str]) -> None:
    import shlex
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


def _get_agent_version() -> str:
    # 1. Try dynamic import from backend app.version
    try:
        project_dir = Path(__file__).resolve().parents[1]
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
        pyproject_path = Path(__file__).resolve().parents[1] / "backend" / "pyproject.toml"
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

    # 4. Fallback default: keep this aligned with backend/pyproject.toml.
    return "0.14.1"
