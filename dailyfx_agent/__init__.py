from __future__ import annotations

import json
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

_original_subprocess_run = subprocess.run

from dailyfx_agent.cli import (
    _build_backend_command,
    _build_parser,
    _build_target_command,
    _parse_args,
    _target_prefix,
    _validate_command_templates,
)
from dailyfx_agent.config import (
    AGENT_QUEUE_DIR,
    IS_TESTING,
    LOCKS_DIR,
    _RECOVERY_DIR_BUFFER_SECONDS,
    _RECOVERY_FILE_BUFFER_SECONDS,
    _DAEMON_STARTUP_TIMEOUT,
)
from dailyfx_agent.daemon import (
    _get_pid_file_path,
    _handle_status,
    _handle_stop,
    _show_single_status,
    _stop_single_daemon,
)
from dailyfx_agent.doctor import (
    _handle_clean_manifests,
    _handle_doctor,
)
from dailyfx_agent.locks import (
    _acquire_lock,
    _release_lock,
    _update_lock_for_daemon_child,
)
from dailyfx_agent.manifest import (
    HOST_METADATA_SOURCE,
    ManifestValidationError,
    _augment_host_prompt,
    _load_manifest,
    _normalize_host_manifest,
    _validate_manifest_schema,
    validate_and_normalize_host_manifest,
)
from dailyfx_agent.models import (
    _get_agy_models,
    _get_codex_models,
    _list_agy_models,
    _list_codex_current_model,
    _list_codex_models,
    _mcp_request,
    _parse_agy_model_line,
    _print_model_list_header,
    _read_jsonrpc_message,
)
from dailyfx_agent.recovery import (
    _find_latest_agy_image,
    _find_latest_codex_image,
    _find_latest_image,
    _validate_output_image,
)
from dailyfx_agent.runner import (
    _copy_task_artifact,
    _rotate_target_logs,
    _run_target_with_spinner,
    _safe_task_id,
    _task_artifact_dir,
    _task_stage_label,
    _task_trace_labels,
    _write_target_log,
    _write_task_json_artifact,
    _write_task_text_artifact,
    main,
)
from dailyfx_agent.utils import (
    _active_process,
    _atomic_write_text,
    _container_to_host_image_path,
    _get_agent_version,
    _print_command,
    _print_note,
    _print_status,
    _print_table,
    _run_subprocess_with_active_tracking,
    _sigterm_handler,
    _terminate_process_gracefully,
)

__all__ = [
    "_active_process",
    "os",
    "sys",
    "subprocess",
    "shutil",
    "re",
    "json",
    "select",
    "signal",
    "tempfile",
    "threading",
    "time",
    "uuid",
    "Path",
    "LOCKS_DIR",
    "AGENT_QUEUE_DIR",
    "_RECOVERY_DIR_BUFFER_SECONDS",
    "_RECOVERY_FILE_BUFFER_SECONDS",
    "_DAEMON_STARTUP_TIMEOUT",
    "IS_TESTING",
    "HOST_METADATA_SOURCE",
    "ManifestValidationError",
    "validate_and_normalize_host_manifest",
    "_validate_manifest_schema",
    "_load_manifest",
    "_normalize_host_manifest",
    "_augment_host_prompt",
    "_atomic_write_text",
    "_sigterm_handler",
    "_terminate_process_gracefully",
    "_run_subprocess_with_active_tracking",
    "_container_to_host_image_path",
    "_get_agent_version",
    "_print_command",
    "_print_note",
    "_print_status",
    "_print_manifest",
    "_print_table",
    "_acquire_lock",
    "_update_lock_for_daemon_child",
    "_release_lock",
    "_parse_agy_model_line",
    "_get_agy_models",
    "_read_jsonrpc_message",
    "_mcp_request",
    "_get_codex_models",
    "_list_agy_models",
    "_list_codex_current_model",
    "_list_codex_models",
    "_find_latest_image",
    "_find_latest_codex_image",
    "_find_latest_agy_image",
    "_validate_output_image",
    "_get_pid_file_path",
    "_show_single_status",
    "_handle_status",
    "_stop_single_daemon",
    "_handle_stop",
    "_handle_clean_manifests",
    "_handle_doctor",
    "_build_parser",
    "_parse_args",
    "_validate_command_templates",
    "_build_backend_command",
    "_build_target_command",
    "_target_prefix",
    "_task_stage_label",
    "_task_trace_labels",
    "_rotate_target_logs",
    "_write_target_log",
    "_safe_task_id",
    "_task_artifact_dir",
    "_write_task_text_artifact",
    "_write_task_json_artifact",
    "_copy_task_artifact",
    "_run_target_with_spinner",
    "main",
]
