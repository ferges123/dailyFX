from __future__ import annotations

import tomllib
from pathlib import Path


def _load_app_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)
    return str(pyproject["project"]["version"])


APP_VERSION = _load_app_version()
