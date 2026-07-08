from __future__ import annotations

import sys
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.config import get_settings

EXAMPLE_SECRET_KEY = "change-me-generate-a-long-random-secret"


def _format_validation_error(exc: ValidationError) -> str:
    details: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "settings"
        message = error.get("msg", "invalid value")
        details.append(f"- {location}: {message}")
    return "Invalid backend configuration:\n" + "\n".join(details)


def _ensure_writable_directory(path: Path, label: str) -> None:
    path.mkdir(parents=True, exist_ok=True)

    probe = path / ".dailyfx-preflight-write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"{label} is not writable: {path}") from exc
    finally:
        probe.unlink(missing_ok=True)


def _check_sqlite_parent_directory(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return

    url = make_url(database_url)
    database_path = url.database
    if not database_path or database_path == ":memory:":
        return

    path = Path(database_path)
    parent = path.parent if path.is_absolute() else Path.cwd() / path.parent
    _ensure_writable_directory(parent, "SQLite database directory")


def run_preflight_checks() -> None:
    try:
        settings = get_settings()
    except ValidationError as exc:
        raise RuntimeError(_format_validation_error(exc)) from exc

    secret_key = settings.secret_key_material.strip()
    if not secret_key:
        raise RuntimeError("APP_SECRET_KEY must not be blank.")
    if secret_key == EXAMPLE_SECRET_KEY:
        if settings.app_env == "production":
            raise RuntimeError(
                "APP_SECRET_KEY must not use the example placeholder value in production. "
                "Please generate a secure random key (e.g., using 'openssl rand -hex 32') "
                "and set it in your environment."
            )
        else:
            print(
                "WARNING: APP_SECRET_KEY still uses the example placeholder value. Replace it before publishing this stack.",
                file=sys.stderr,
            )

    _ensure_writable_directory(settings.data_dir, "DATA_DIR")
    _check_sqlite_parent_directory(settings.database_url)

    print(
        f"Preflight OK: data_dir={settings.data_dir} database_url={settings.database_url}",
        file=sys.stderr,
    )


def main() -> None:
    try:
        run_preflight_checks()
    except Exception as exc:
        print(f"Preflight failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
