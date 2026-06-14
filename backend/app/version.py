from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path


def _load_app_version() -> str:
    try:
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        if pyproject_path.exists():
            with pyproject_path.open("rb") as pyproject_file:
                pyproject = tomllib.load(pyproject_file)
            return str(pyproject["project"]["version"])
    except Exception:
        pass

    try:
        return importlib.metadata.version("dailyfx-backend")
    except Exception:
        pass

    return "0.3.0"


APP_VERSION = _load_app_version()
