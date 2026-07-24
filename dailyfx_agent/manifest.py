from __future__ import annotations

import json
import importlib
import importlib.util
import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parents[1]
_backend_dir = _script_dir / "backend"
_host_manifest_path = _backend_dir / "app" / "services" / "generation" / "host_manifest.py"
_host_manifest_module = sys.modules.get("app.services.generation.host_manifest")
if _host_manifest_module is None and not _host_manifest_path.exists():
    _host_manifest_module = importlib.import_module(
        "app.services.generation.host_manifest"
    )
if _host_manifest_module is None:
    _host_manifest_spec = importlib.util.spec_from_file_location(
        "app.services.generation.host_manifest", _host_manifest_path
    )
    if _host_manifest_spec is None or _host_manifest_spec.loader is None:
        raise ImportError(f"Unable to load host manifest validator: {_host_manifest_path}")
    _host_manifest_module = importlib.util.module_from_spec(_host_manifest_spec)
    sys.modules["app.services.generation.host_manifest"] = _host_manifest_module
    _host_manifest_spec.loader.exec_module(_host_manifest_module)

HOST_METADATA_SOURCE = _host_manifest_module.HOST_METADATA_SOURCE
validate_and_normalize_host_manifest = _host_manifest_module.validate_and_normalize_host_manifest
ManifestValidationError = _host_manifest_module.ManifestValidationError


def _validate_manifest_schema(manifest: object) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("Manifest is not a JSON object")

    for field in ("task_id", "output_path"):
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Manifest validation error: required field '{field}' is missing or empty")

    type_checks = {
        "task_id": (str, "string"),
        "status": (str, "string"),
        "generation_type": (str, "string"),
        "title": (str, "string"),
        "summary": (str, "string"),
        "prompt": (str, "string"),
        "handoff_prompt": (str, "string"),
        "source_image_path": (str, "string"),
        "host_relative_image_path": (str, "string"),
        "output_path": (str, "string"),
        "image_path": (str, "string"),
        "source_asset_id": (str, "string"),
        "source_asset_original_file_name": (str, "string"),
        "config_json": (dict, "object"),
        "tags": (list, "array"),
        "task_trace": (list, "array"),
    }

    for field, (expected_type, type_name) in type_checks.items():
        if field in manifest:
            value = manifest[field]
            if value is not None and not isinstance(value, expected_type):
                raise ValueError(
                    f"Manifest validation error: field '{field}' must be a {type_name}, got {type(value).__name__}"
                )


def _load_manifest(path: Path) -> dict[str, object]:
    payload = path.read_text(encoding="utf-8")
    try:
        manifest = json.loads(payload)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in manifest file: {e}") from e
    _validate_manifest_schema(manifest)
    return manifest


def _normalize_host_manifest(
    manifest: object, original_manifest: object | None = None
) -> dict[str, object]:
    if not isinstance(manifest, dict):
        raise ValueError("Host manifest is not a JSON object")
    return validate_and_normalize_host_manifest(manifest, original_manifest)


def _augment_host_prompt(
    original_prompt: str,
    abs_image_path: str,
    abs_manifest_path: str,
    abs_output_path: str,
    task_id: str,
) -> str:
    source_str = HOST_METADATA_SOURCE
    checklist = (
        f"\n\nCRITICAL SYSTEM INSTRUCTION: THIS IS NOT A SOFTWARE DEVELOPMENT, CODING, OR TESTING TASK. "
        f"DO NOT look at the git status, DO NOT read files from the repository (e.g., Python source code files), "
        f"DO NOT run any tests (like pytest), and DO NOT execute any make commands (such as make test, make lint, or make *). "
        f"Focus EXCLUSIVELY on generating the requested image and writing/updating the metadata. "
        f"Do not attempt to verify or review the codebase code.\n\n"
        f"CRITICAL: As the AI agent running on the host, you MUST follow this checklist:\n"
        f"Checklist:\n"
        f"- [ ] Source Vision: Open and analyze the input image (source photo) at '{abs_image_path}' to extract context, theme, and subjects.\n"
        f"- [ ] Image Generation: Apply the requested effects/modifications and save the final output image exactly at '{abs_output_path}' (or in a directory/filename containing the task ID '{task_id}').\n"
        f"- [ ] Final Vision: Open and analyze the saved output image at '{abs_output_path}' to evaluate quality, aesthetics, and theme match.\n"
        f"- [ ] Manifest Update: Write/update the local JSON manifest file at '{abs_manifest_path}' with the following keys:\n"
        f"  * 'title' (short, creative 3-5 word title)\n"
        f"  * 'summary' (one concise sentence describing the final image)\n"
        f"  * 'tags' (a JSON array containing 3-6 descriptive keywords)\n"
        f"  * 'metadata_source' (must be set to '{source_str}')\n"
        f"\n"
        f"Technical Rules:\n"
        f"1. DO NOT modify any other technical/system keys in the JSON manifest.\n"
        f"2. Ensure the JSON written to '{abs_manifest_path}' is standard and correctly structured.\n"
        f"3. Make sure the output file is saved at '{abs_output_path}' before finalizing."
    )
    return original_prompt + checklist
