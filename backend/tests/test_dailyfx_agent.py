from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from io import BytesIO, StringIO
from pathlib import Path
from subprocess import CompletedProcess

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dailyfx_agent  # noqa: E402


def _png_bytes(color=(12, 34, 56)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _seed_agy_generated_image(tmp_path, filename="desert_diorama_123.jpg"):
    generated_root = tmp_path / ".gemini" / "antigravity-cli" / "brain" / "session-1"
    generated_root.mkdir(parents=True)
    image_path = generated_root / filename
    image_path.write_bytes(_png_bytes())
    os.utime(image_path, (time.time() + 100, time.time() + 100))
    return image_path


def _write_updated_host_manifest(tmp_path, manifest, title="Updated Family Stroll"):
    updated_manifest = dict(manifest)
    updated_manifest["title"] = title
    updated_manifest["summary"] = "A refreshed final vision summary."
    updated_manifest["tags"] = ["family", "portrait", "claymation"]
    updated_manifest["metadata_source"] = "host_agent_final_vision"
    (tmp_path / "run.json").write_text(json.dumps(updated_manifest), encoding="utf-8")


def _write_host_manifest_without_metadata_source(tmp_path, manifest, title="Updated Family Stroll"):
    updated_manifest = dict(manifest)
    updated_manifest["title"] = title
    updated_manifest["summary"] = "A refreshed final vision summary."
    updated_manifest["tags"] = ["family", "portrait", "claymation"]
    updated_manifest.pop("metadata_source", None)
    (tmp_path / "run.json").write_text(json.dumps(updated_manifest), encoding="utf-8")


def test_container_to_host_image_path_translates_data_prefix():
    assert dailyfx_agent._container_to_host_image_path("/data/results/run-1.png") == "./data/results/run-1.png"
    assert dailyfx_agent._container_to_host_image_path("/tmp/run-1.png") == "/tmp/run-1.png"


def test_dailyfx_agent_runs_backend_then_target(monkeypatch, tmp_path, capsys):
    manifest = {
        "task_id": "cli-s1-abc123",
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "source_asset_id": "asset-1",
        "source_asset_original_file_name": "source.jpg",
        "config_json": {},
        "tags": ["family", "portrait", "claymation"],
        "task_trace": [
            {"stage": "selecting_asset", "message": "Searching for photos…", "progress": 0.1},
            {"stage": "applying_effect", "message": "Applying effect…", "progress": 0.25},
        ],
    }
    backend_stdout = json.dumps(manifest)
    calls: list[list[str]] = []
    inputs: list[str | None] = []
    _seed_agy_generated_image(tmp_path)

    def fake_run(command, **kwargs):
        calls.append(command)
        inputs.append(kwargs.get("input"))
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] in {"agy", "codex"}:
            _write_updated_host_manifest(tmp_path, manifest)
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent.time, "time", lambda: 1000.0)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "agy",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(tmp_path / "run.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls[0][:4] == ["docker", "compose", "-f", "docker-compose.yml"]
    assert calls[0][8:10] == ["prepare-host", "--schedule-id"]
    assert calls[1] == [
        "agy",
        "--print",
        "--image",
        "./data/results/cli-s1-abc123.input.png",
    ]
    assert inputs[1] and inputs[1].startswith("Use the image.")
    assert calls[2][8:10] == ["finalize-host", "--manifest-path"]
    saved_manifest = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert saved_manifest["title"] == "Updated Family Stroll"
    assert saved_manifest["summary"] == "A refreshed final vision summary."
    assert saved_manifest["tags"] == ["family", "portrait", "claymation"]
    assert saved_manifest["metadata_source"] == "host_agent_final_vision"
    assert "image provider: agy" in captured.out
    assert "done: ./data/results/cli-s1-abc123.png" in captured.out


def test_dailyfx_agent_requires_updated_metadata_before_finalize(monkeypatch, tmp_path, capsys):
    manifest = {
        "task_id": "cli-s1-abc123",
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "source_asset_id": "asset-1",
        "source_asset_original_file_name": "source.jpg",
        "config_json": {},
        "tags": ["family", "portrait", "claymation"],
        "task_trace": [{"stage": "queued", "message": "Queued for host run", "progress": 0.0}],
    }
    backend_stdout = json.dumps(manifest)
    calls: list[list[str]] = []
    _seed_agy_generated_image(tmp_path)

    def fake_run(command, **kwargs):
        calls.append(command)
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] in {"agy", "codex"}:
            _write_host_manifest_without_metadata_source(tmp_path, manifest)
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent.time, "time", lambda: 1000.0)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "agy",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(tmp_path / "run.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert any(command and command[0] == "agy" for command in calls)
    assert not any("finalize-host" in command for command in calls)
    assert "metadata_source" in captured.err


def test_dailyfx_agent_hides_target_thinking_output(monkeypatch, tmp_path, capsys):
    manifest = {
        "task_id": "cli-s1-abc123",
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "source_asset_id": "asset-1",
        "source_asset_original_file_name": "source.jpg",
        "config_json": {},
        "task_trace": [{"stage": "queued", "message": "Queued for host run", "progress": 0.0}],
    }
    backend_stdout = json.dumps(manifest)
    calls: list[list[str]] = []
    _seed_agy_generated_image(tmp_path)

    def fake_run(command, **kwargs):
        calls.append(command)
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] == "agy":
            _write_updated_host_manifest(tmp_path, manifest)
            return CompletedProcess(
                command,
                0,
                stdout="OpenAI Codex\nthinking: internal chain of thought\nI have generated the image.\n",
                stderr="",
            )
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent.time, "time", lambda: 1000.0)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "agy",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(tmp_path / "run.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "image provider: agy" in captured.out
    assert "thinking: internal chain of thought" not in captured.out
    assert "I have generated the image." not in captured.out
    assert "done: ./data/results/cli-s1-abc123.png" in captured.out


def test_task_trace_labels_use_short_stage_markers():
    labels = dailyfx_agent._task_trace_labels(
        [
            {"stage": "selecting_asset", "message": "Searching for photos…", "progress": 0.1},
            {"stage": "applying_effect", "message": "Applying effect…", "progress": 0.25},
            {"stage": "saving_result", "message": "Saving result…", "progress": 0.95},
        ]
    )

    assert labels == [
        "[search] 10% Searching for photos…",
        "[render] 25% Applying effect…",
        "[save] 95% Saving result…",
    ]


def test_dailyfx_agent_dry_run_shows_backend_and_target_commands(monkeypatch, capsys):
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        raise AssertionError("dry-run should not execute subprocesses")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "7",
            "--target",
            "codex",
            "--dry-run",
            "--codex-command-template",
            "exec --image {image_path} -",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == []
    assert (
        "backend: docker compose -f docker-compose.yml exec -T api dailyfx prepare-host --schedule-id 7 --target codex"
        in captured.out
    )
    assert "target: codex exec --image '{image_path}' -" in captured.out
    assert (
        "finalize: docker compose -f docker-compose.yml exec -T api dailyfx finalize-host --manifest-path /data/dailyfx-run-"
        in captured.out
    )
    assert ".json" in captured.out
    assert "Dry-run does not execute docker compose or the host tool." in captured.out


def test_dailyfx_agent_lists_schedules(monkeypatch, capsys):
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return CompletedProcess(
            command, 0, stdout="ID\tNAME\tENABLED\n1\tMorning Run\tyes\n2\tNight Run\tno\n", stderr=""
        )

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)

    exit_code = dailyfx_agent.main(["--list-schedules"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls[0] == ["docker", "compose", "-f", "docker-compose.yml", "exec", "-T", "api", "dailyfx", "schedules"]
    assert "Morning Run" in captured.out
    assert "Night Run" in captured.out


def test_dailyfx_agent_supports_short_aliases(monkeypatch, tmp_path):
    manifest = {
        "task_id": "cli-s1-abc123",
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "source_asset_id": "asset-1",
        "source_asset_original_file_name": "source.jpg",
        "config_json": {},
        "tags": ["family", "portrait", "claymation"],
    }
    backend_stdout = json.dumps(manifest)
    calls: list[list[str]] = []
    inputs: list[str | None] = []
    _seed_agy_generated_image(tmp_path)

    def fake_run(command, **kwargs):
        calls.append(command)
        inputs.append(kwargs.get("input"))
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] in {"agy", "codex"}:
            _write_updated_host_manifest(tmp_path, manifest)
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent.time, "time", lambda: 1000.0)

    exit_code = dailyfx_agent.main(
        [
            "-s",
            "1",
            "-t",
            "agy",
            "-v",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(tmp_path / "run.json"),
        ]
    )

    assert exit_code == 0
    assert calls[1] == [
        "agy",
        "--print",
        "--image",
        "./data/results/cli-s1-abc123.input.png",
    ]
    assert inputs[1] and inputs[1].startswith("Use the image.")


def test_dailyfx_agent_passes_model_to_agy(monkeypatch, tmp_path):
    manifest = {
        "task_id": "cli-s1-abc123",
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "source_asset_id": "asset-1",
        "source_asset_original_file_name": "source.jpg",
        "config_json": {},
        "tags": ["family", "portrait", "claymation"],
    }
    backend_stdout = json.dumps(manifest)
    calls: list[list[str]] = []
    _seed_agy_generated_image(tmp_path)

    def fake_run(command, **kwargs):
        calls.append(command)
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] in {"agy", "codex"}:
            _write_updated_host_manifest(tmp_path, manifest)
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent.time, "time", lambda: 1000.0)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "agy",
            "--model",
            "gpt-5.5",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(tmp_path / "run.json"),
        ]
    )

    assert exit_code == 0
    assert calls[1][:4] == ["agy", "--model", "gpt-5.5", "--print"]


def test_dailyfx_agent_passes_model_to_codex(monkeypatch, tmp_path):
    manifest = {
        "task_id": "cli-s1-abc123",
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "source_asset_id": "asset-1",
        "source_asset_original_file_name": "source.jpg",
        "config_json": {},
        "tags": ["family", "portrait", "claymation"],
    }
    backend_stdout = json.dumps(manifest)
    generated_root = tmp_path / ".codex" / "generated_images" / "session-1"
    generated_root.mkdir(parents=True)
    codex_image = generated_root / "ig_test.png"
    codex_image.write_bytes(_png_bytes())
    os.utime(codex_image, (time.time() + 100, time.time() + 100))
    calls: list[list[str]] = []
    inputs: list[str | None] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        inputs.append(kwargs.get("input"))
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] in {"agy", "codex"}:
            _write_updated_host_manifest(tmp_path, manifest)
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent.time, "time", lambda: 1000.0)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(tmp_path / "run.json"),
        ]
    )

    assert exit_code == 0
    assert calls[1][:4] == ["codex", "-m", "gpt-5.5", "exec"]
    assert inputs[1] and inputs[1].startswith("Use the image.")


def test_dailyfx_agent_lists_models_for_target(monkeypatch, capsys):
    agy_called = {"value": False}
    codex_called = {"value": False}

    monkeypatch.setattr(dailyfx_agent, "_list_agy_models", lambda: agy_called.__setitem__("value", True) or 0)
    monkeypatch.setattr(dailyfx_agent, "_list_codex_models", lambda: codex_called.__setitem__("value", True) or 0)

    exit_code = dailyfx_agent.main(["--list-models", "--target", "agy"])
    assert exit_code == 0
    assert agy_called["value"] is True
    assert codex_called["value"] is False
    assert "agy models:" in capsys.readouterr().out

    agy_called["value"] = False
    codex_called["value"] = False
    exit_code = dailyfx_agent.main(["--list-models", "--target", "codex"])
    assert exit_code == 0
    assert agy_called["value"] is False
    assert codex_called["value"] is True
    assert "codex models:" in capsys.readouterr().out


def test_list_agy_models_renders_table(monkeypatch, capsys):
    def fake_run(command, **kwargs):
        return CompletedProcess(command, 0, stdout="Gemini 3.5 Flash (Medium)\nGemini 3.1 Pro (High)\n", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)

    exit_code = dailyfx_agent._list_agy_models()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "ID" in output and "NAME" in output and "REASONING" in output and "DEFAULT" in output
    assert "Gemini 3.5 Flash" in output
    assert "Medium" in output


def test_list_codex_models_renders_table(monkeypatch, capsys):
    class FakePopen:
        def __init__(self, *args, **kwargs):
            self.stdin = StringIO()
            self.stdout = StringIO()
            self.stderr = StringIO()

        def terminate(self):
            return None

    responses = [
        {
            "result": {},
        },
        {
            "result": {
                "data": [
                    {
                        "model": "gpt-5.5",
                        "displayName": "GPT-5.5",
                        "isDefault": True,
                        "supportedReasoningEfforts": [{"reasoningEffort": "low"}],
                    },
                    {
                        "model": "gpt-5.4-mini",
                        "displayName": "GPT-5.4 Mini",
                        "isDefault": False,
                        "supportedReasoningEfforts": [{"reasoningEffort": "medium"}],
                    },
                ],
                "nextCursor": None,
            },
        },
    ]

    def fake_mcp_request(proc, request_id, method, params=None, **kwargs):
        return responses.pop(0)["result"]

    monkeypatch.setattr(dailyfx_agent.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(dailyfx_agent, "_mcp_request", fake_mcp_request)

    exit_code = dailyfx_agent._list_codex_models()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "ID" in output and "NAME" in output and "REASONING" in output and "DEFAULT" in output
    assert "gpt-5.5" in output
    assert "GPT-5.4 Mini" in output
    assert "yes" in output
    assert "low" in output


def test_list_codex_models_falls_back_to_doctor_when_catalog_unavailable(monkeypatch, capsys):
    class FakePopen:
        def __init__(self, *args, **kwargs):
            self.stdin = StringIO()
            self.stdout = StringIO()
            self.stderr = StringIO()

        def terminate(self):
            return None

    def fake_mcp_request(proc, request_id, method, params=None, **kwargs):
        raise RuntimeError("{'code': -32601, 'message': 'method not found: model/list'}")

    def fake_run(command, **kwargs):
        if command == ["codex", "doctor"]:
            return CompletedProcess(
                command,
                0,
                stdout="Configuration\n  ✓ config       loaded\n      model                    gpt-5.5 · openai\n",
                stderr="",
            )
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent, "_mcp_request", fake_mcp_request)

    exit_code = dailyfx_agent._list_codex_models()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "current configured model" in output
    assert "gpt-5.5" in output
    assert "openai" in output


def test_dailyfx_agent_shows_help_without_arguments(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["dailyfx-agent"])

    exit_code = dailyfx_agent.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "dailyfx-agent" in captured.out
    assert "--list-schedules" in captured.out
    assert "--schedule-id" in captured.out
    assert "Examples:" in captured.out


def test_dailyfx_agent_renders_agy_template(monkeypatch, tmp_path, capsys):
    manifest = {
        "task_id": "cli-s1-abc123",
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "source_asset_id": "asset-1",
        "source_asset_original_file_name": "source.jpg",
        "config_json": {},
        "tags": ["family", "portrait", "claymation"],
    }
    backend_stdout = json.dumps(manifest)
    calls: list[list[str]] = []
    inputs: list[str | None] = []
    _seed_agy_generated_image(tmp_path)

    def fake_run(command, **kwargs):
        calls.append(command)
        inputs.append(kwargs.get("input"))
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] in {"agy", "codex"}:
            _write_updated_host_manifest(tmp_path, manifest)
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent.time, "time", lambda: 1000.0)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "agy",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(tmp_path / "run.json"),
            "--agy-command-template",
            "--print --image {image_path}",
            "--verbose",
        ]
    )

    assert exit_code == 0
    assert calls[1] == [
        "agy",
        "--print",
        "--image",
        "./data/results/cli-s1-abc123.input.png",
    ]
    assert inputs[1] and inputs[1].startswith("Use the image.")
    # Verbose mode prints the manifest to stderr.
    assert '"task_id": "cli-s1-abc123"' in capsys.readouterr().err


def test_dailyfx_agent_copies_codex_generated_image_when_output_is_missing(
    monkeypatch,
    tmp_path,
):
    manifest = {
        "task_id": "cli-s1-abc123",
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "source_asset_id": "asset-1",
        "source_asset_original_file_name": "source.jpg",
        "config_json": {},
        "tags": ["family", "portrait", "claymation"],
    }
    backend_stdout = json.dumps(manifest)
    generated_root = tmp_path / ".codex" / "generated_images" / "session-1"
    generated_root.mkdir(parents=True)
    codex_image = generated_root / "ig_test.png"
    codex_image.write_bytes(_png_bytes())
    os.utime(codex_image, (time.time() + 100, time.time() + 100))
    calls: list[list[str]] = []
    inputs: list[str | None] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        inputs.append(kwargs.get("input"))
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] in {"agy", "codex"}:
            _write_updated_host_manifest(tmp_path, manifest)
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent.time, "time", lambda: 1000.0)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "codex",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(tmp_path / "run.json"),
        ]
    )

    assert exit_code == 0
    assert inputs[1] and inputs[1].startswith("Use the image.")
    output_path = tmp_path / "data" / "results" / "cli-s1-abc123.png"
    assert output_path.read_bytes() == codex_image.read_bytes()


def test_dailyfx_agent_copies_agy_generated_image_when_output_is_missing(
    monkeypatch,
    tmp_path,
):
    manifest = {
        "task_id": "cli-s1-abc123",
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "source_asset_id": "asset-1",
        "source_asset_original_file_name": "source.jpg",
        "config_json": {},
    }
    backend_stdout = json.dumps(manifest)
    generated_root = tmp_path / ".gemini" / "antigravity-cli" / "brain" / "session-1"
    generated_root.mkdir(parents=True)
    agy_image = generated_root / "desert_diorama_123.jpg"
    agy_image.write_bytes(_png_bytes())
    os.utime(agy_image, (time.time() + 100, time.time() + 100))
    calls: list[list[str]] = []
    inputs: list[str | None] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        inputs.append(kwargs.get("input"))
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] in {"agy", "codex"}:
            _write_updated_host_manifest(tmp_path, manifest)
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent.time, "time", lambda: 1000.0)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "agy",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(tmp_path / "run.json"),
        ]
    )

    assert exit_code == 0
    assert inputs[1] and inputs[1].startswith("Use the image.")
    output_path = tmp_path / "data" / "results" / "cli-s1-abc123.png"
    assert output_path.read_bytes() == agy_image.read_bytes()


def test_dailyfx_agent_warns_on_quoted_placeholders_in_templates(monkeypatch, capsys):
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        raise AssertionError("dry-run should not execute subprocesses")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "7",
            "--target",
            "codex",
            "--dry-run",
            "--codex-command-template",
            "exec --image '{image_path}' -",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert (
        "warning: Custom template 'codex-command-template' contains quoted placeholder '{image_path}'." in captured.err
    )


def test_run_target_with_spinner_clears_terminal_line(monkeypatch):
    stderr_mock = StringIO()
    monkeypatch.setattr(sys, "stderr", stderr_mock)

    result, log_path = dailyfx_agent._run_target_with_spinner(["true"], prompt="", task_id="test", labels=["label1"])

    captured = stderr_mock.getvalue()
    assert "\033[K" in captured
    assert "\r\033[K" in captured


def test_list_codex_models_redirects_stderr_to_devnull(monkeypatch):
    import subprocess

    popen_args = []

    class FakePopen:
        def __init__(self, command, **kwargs):
            popen_args.append((command, kwargs))
            self.stdin = type("obj", (object,), {"write": lambda s, data: None, "flush": lambda s: None})()

            class CustomList(list):
                pass

            self.stdout = CustomList()
            self.stderr = []
            self.returncode = 0

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(dailyfx_agent.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(dailyfx_agent, "_mcp_request", lambda *args, **kwargs: {"data": []})

    dailyfx_agent._list_codex_models()
    assert popen_args[0][1].get("stderr") == subprocess.DEVNULL


def test_daemon_mode_performs_os_level_fd_redirection(monkeypatch):
    dup2_calls = []
    setsid_called = []

    monkeypatch.setattr(dailyfx_agent.os, "fork", lambda: 0)  # Symulacja dziecka
    monkeypatch.setattr(dailyfx_agent.os, "setsid", lambda: setsid_called.append(True))
    monkeypatch.setattr(dailyfx_agent.os, "dup2", lambda fd1, fd2: dup2_calls.append((fd1, fd2)))
    monkeypatch.setattr(
        dailyfx_agent,
        "_parse_args",
        lambda argv: dailyfx_agent._build_parser().parse_args(["--daemon", "--schedule-id", "1", "--target", "agy"]),
    )

    # Zamakowanie reszty maina, by nie wywoływał komend Dockera
    monkeypatch.setattr(dailyfx_agent, "_build_backend_command", lambda args: [])
    monkeypatch.setattr(
        dailyfx_agent.subprocess,
        "run",
        lambda *args, **kwargs: type("obj", (object,), {"returncode": 0, "stdout": "{}", "stderr": ""}),
    )
    monkeypatch.setattr(dailyfx_agent, "_load_manifest", lambda path: {})

    try:
        dailyfx_agent.main(["--daemon", "--schedule-id", "1", "--target", "agy"])
    except SystemExit:
        pass

    # Sprawdzenie czy dup2 przekierował FD 0, 1, 2
    fds = [fd_target for _, fd_target in dup2_calls]
    assert 0 in fds
    assert 1 in fds
    assert 2 in fds


def test_main_cleans_up_manifests_on_exception(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dailyfx_agent.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(dailyfx_agent, "_build_backend_command", lambda args: ["true"])

    from subprocess import CompletedProcess

    def fake_run(command, **kwargs):
        if command == ["true"]:
            return CompletedProcess(command, 0, stdout="{}", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)

    def fake_load_manifest(path):
        raise ValueError("Force crash inside loop")

    monkeypatch.setattr(dailyfx_agent, "_load_manifest", fake_load_manifest)

    try:
        dailyfx_agent.main(["--schedule-id", "1", "--target", "agy", "--project-dir", str(tmp_path)])
    except ValueError as exc:
        assert str(exc) == "Force crash inside loop"

    temp_files = list(tmp_path.glob("dailyfx-run-*.json"))
    assert len(temp_files) == 0

    shared_temp_files = list(Path("data").glob("dailyfx-run-*.json"))
    assert len(shared_temp_files) == 0


def test_read_jsonrpc_message_without_queue_raises_runtime_error():
    import pytest

    class FakeStream:
        pass

    with pytest.raises(RuntimeError, match="Stream does not have a response queue attached"):
        dailyfx_agent._read_jsonrpc_message(FakeStream())


def test_run_target_with_spinner_skips_spinner_in_daemon_mode(monkeypatch):
    spinner_thread_started = False

    import threading

    original_thread = threading.Thread

    def fake_thread_start(self):
        nonlocal spinner_thread_started
        if "spinner" in str(self._target):
            spinner_thread_started = True
        return original_thread.start(self)

    monkeypatch.setattr(threading.Thread, "start", fake_thread_start)
    monkeypatch.setattr(
        dailyfx_agent.subprocess,
        "run",
        lambda *args, **kwargs: type("obj", (object,), {"returncode": 0, "stdout": "", "stderr": ""}),
    )

    dailyfx_agent._run_target_with_spinner(["echo"], prompt="", task_id="test", labels=[], daemon_mode=True)
    assert not spinner_thread_started


def test_dailyfx_agent_repeat_runs_multiple_times(monkeypatch, tmp_path):
    manifest = {
        "task_id": "cli-s1-abc123",
        "schedule_id": 1,
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "source_asset_id": "asset-1",
        "source_asset_original_file_name": "source.jpg",
        "config_json": {},
        "tags": ["family", "portrait", "claymation"],
        "target": "agy",
    }
    backend_stdout = json.dumps(manifest)
    calls: list[list[str]] = []

    _seed_agy_generated_image(tmp_path)

    def fake_run(command, **kwargs):
        calls.append(command)
        if "dailyfx" in command:
            if "finalize-host" in command:
                manifest_file = Path(command[-1])
                local_manifest_file = Path("data") / manifest_file.name
                if not local_manifest_file.is_absolute():
                    local_manifest_file = Path(kwargs.get("cwd", ".")) / local_manifest_file
                if local_manifest_file.exists():
                    payload = json.loads(local_manifest_file.read_text(encoding="utf-8"))
                    assert payload.get("target") == "agy"
                    assert payload.get("task_id") == "cli-s1-abc123"
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] in {"agy", "codex"}:
            updated = {
                "title": "Updated Family Stroll",
                "summary": "A refreshed final vision summary.",
                "tags": ["family", "portrait", "claymation"],
                "metadata_source": "host_agent_final_vision",
            }
            (tmp_path / "run.json").write_text(json.dumps(updated), encoding="utf-8")
            (tmp_path / "run-run2.json").write_text(json.dumps(updated), encoding="utf-8")
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent.time, "time", lambda: 1000.0)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "agy",
            "--repeat",
            "2",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(tmp_path / "run.json"),
        ]
    )

    assert exit_code == 0
    assert len(calls) == 6
    assert calls[0][8:10] == ["prepare-host", "--schedule-id"]
    assert calls[1][0] == "agy"
    assert calls[2][8:10] == ["finalize-host", "--manifest-path"]
    assert calls[3][8:10] == ["prepare-host", "--schedule-id"]
    assert calls[4][0] == "agy"
    assert calls[5][8:10] == ["finalize-host", "--manifest-path"]


def test_target_log_stored_in_workspace(monkeypatch, tmp_path):
    log_dir_arg = None

    def fake_write_target_log(*, log_dir, **kwargs):
        nonlocal log_dir_arg
        log_dir_arg = log_dir
        return tmp_path / "fake.log"

    monkeypatch.setattr(dailyfx_agent, "_write_target_log", fake_write_target_log)
    monkeypatch.setattr(
        dailyfx_agent,
        "_run_subprocess_with_active_tracking",
        lambda *a, **kw: CompletedProcess(["echo"], 0, stdout="test", stderr=""),
    )

    dailyfx_agent._run_target_with_spinner(["echo"], prompt="", task_id="test", labels=[], daemon_mode=True)
    assert log_dir_arg == Path("data") / "logs" / "agent"


def test_sigterm_kills_subprocess(monkeypatch):
    import signal

    kill_called = False

    class FakeProc:
        def kill(self):
            nonlocal kill_called
            kill_called = True

    proc = FakeProc()
    monkeypatch.setattr(dailyfx_agent, "_active_process", proc)

    try:
        dailyfx_agent._sigterm_handler(signal.SIGTERM, None)
    except SystemExit as exc:
        assert exc.code == 128 + signal.SIGTERM

    assert kill_called is True


def test_model_validation_fails_on_invalid_model(monkeypatch, capsys):
    monkeypatch.setattr(dailyfx_agent, "_get_agy_models", lambda *a: ["gemini-3.5-flash"])
    exit_code = dailyfx_agent.main(["--schedule-id", "1", "--target", "agy", "--model", "invalid-model"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: Model 'invalid-model' is not available for target 'agy'" in captured.err


def test_manifest_cleanup_unconditional(monkeypatch, tmp_path):
    manifest_file = tmp_path / "dailyfx-run-custom.json"
    manifest_file.write_text(json.dumps({"task_id": "test"}), encoding="utf-8")

    monkeypatch.setattr(dailyfx_agent, "_validate_command_templates", lambda *a: None)

    manifest = {
        "task_id": "cli-s1-abc123",
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": str(tmp_path / "out.input.png"),
        "output_path": str(tmp_path / "out.png"),
        "source_asset_id": "asset-1",
        "source_asset_original_file_name": "source.jpg",
        "config_json": {},
        "tags": ["family"],
        "task_trace": [],
    }

    def fake_run(command, **kwargs):
        if "prepare-host" in command or "finalize-host" in command:
            return CompletedProcess(command, 0, stdout=json.dumps(manifest), stderr="")
        if command and command[0] in {"agy", "codex", "echo"}:
            updated = dict(manifest)
            updated["title"] = "Updated Title"
            updated["summary"] = "A summary"
            updated["tags"] = ["family", "portrait", "claymation"]
            updated["metadata_source"] = "host_agent_final_vision"
            manifest_file.write_text(json.dumps(updated), encoding="utf-8")
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    (tmp_path / "out.png").write_bytes(_png_bytes())
    (tmp_path / "out.input.png").write_bytes(_png_bytes())
    _seed_agy_generated_image(tmp_path)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "agy",
            "--manifest-path",
            str(manifest_file),
            "--project-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert not manifest_file.exists()


def test_manifest_schema_validation(tmp_path):
    manifest_file = tmp_path / "invalid-manifest.json"
    manifest_file.write_text(
        json.dumps({"task_id": "test", "task_trace": "invalid_string_instead_of_list"}), encoding="utf-8"
    )

    import pytest

    with pytest.raises(ValueError, match="field 'task_trace' must be a array"):
        dailyfx_agent._load_manifest(manifest_file)


def test_dailyfx_agent_uses_shared_validation():
    import pytest

    from app.services.generation.host_manifest import ManifestValidationError

    # We expect _normalize_host_manifest to raise ManifestValidationError (a subclass of ValueError)
    # when validation fails (e.g. empty manifest).
    with pytest.raises(ManifestValidationError):
        dailyfx_agent._normalize_host_manifest({})


def test_prompt_augmentation(monkeypatch, tmp_path):
    manifest = {
        "task_id": "test-task-12345",
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Miniature Family Stroll",
        "summary": "Use the image.",
        "prompt": "Base Prompt Text",
        "source_image_path": str(tmp_path / "source.png"),
        "output_path": str(tmp_path / "output.png"),
        "source_asset_id": "asset-1",
        "tags": ["family", "portrait", "claymation"],
        "task_trace": [],
    }
    backend_stdout = json.dumps(manifest)
    (tmp_path / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "output.png").write_bytes(_png_bytes())

    captured_prompt = []

    def fake_run(command, **kwargs):
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    def fake_run_spinner(command, prompt, task_id, labels, timeout=None, daemon_mode=False):
        captured_prompt.append(prompt)
        # Create updated manifest
        updated = dict(manifest)
        updated["metadata_source"] = "host_agent_final_vision"
        updated["title"] = "Updated Title"
        updated["summary"] = "Updated Summary"
        updated["tags"] = ["tag1", "tag2", "tag3"]
        (tmp_path / "run.json").write_text(json.dumps(updated), encoding="utf-8")
        return CompletedProcess(command, 0, stdout="", stderr=""), "/tmp/log"

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent, "_run_target_with_spinner", fake_run_spinner)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "agy",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(tmp_path / "run.json"),
        ]
    )

    assert exit_code == 0
    assert len(captured_prompt) == 1
    prompt = captured_prompt[0]
    assert "Base Prompt Text" in prompt
    assert "test-task-12345" in prompt
    assert "output.png" in prompt


def test_find_latest_image_prioritizes_task_id(tmp_path, capsys):
    generated_root = tmp_path / "gen"
    generated_root.mkdir()

    now = time.time()

    # Image A: matches task_id 'task123', older
    img_a = generated_root / "render_task123_output.png"
    img_a.write_bytes(b"matching")
    os.utime(img_a, (now + 10, now + 10))

    # Image B: does not match task_id 'task123', newer
    img_b = generated_root / "render_other_output.png"
    img_b.write_bytes(b"newer")
    os.utime(img_b, (now + 20, now + 20))

    # Expect Image A to be returned since it matches task_id 'task123'
    recovered_a = dailyfx_agent._find_latest_image(start_time=now, generated_root=generated_root, task_id="task123")
    assert recovered_a == img_a

    # Clean up captured warnings
    capsys.readouterr()

    # Expect Image B to be returned when task_id is 'another_task'
    # and a warning to be printed in stderr
    recovered_b = dailyfx_agent._find_latest_image(
        start_time=now, generated_root=generated_root, task_id="another_task"
    )
    assert recovered_b == img_b
    captured = capsys.readouterr()
    assert "warning:" in captured.err
    assert "another_task" in captured.err


def test_daemon_status_and_stop(tmp_path, capsys):
    pid_file = tmp_path / "test.pid"
    metadata_file = tmp_path / "test.pid.json"

    # 1. Status: no PID file
    exit_code = dailyfx_agent.main(["--status", "--pid-file", str(pid_file)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "status: stopped (no PID file)" in captured.out

    # 2. Status: stale (dead) PID file
    # We write a PID that doesn't exist (e.g. 999999)
    pid_file.write_text("999999", encoding="utf-8")
    metadata_file.write_text(
        json.dumps(
            {
                "pid": 999999,
                "schedule_id": 42,
                "target": "agy",
                "started_at": "2026-07-09T13:00:00Z",
                "log_path": "/tmp/test.log",
                "manifest_path": "/tmp/manifest.json",
            }
        ),
        encoding="utf-8",
    )

    exit_code = dailyfx_agent.main(["--status", "--pid-file", str(pid_file)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "status: stopped (stale PID file)" in captured.out
    assert "pid: 999999" in captured.out
    assert "schedule_id: 42" in captured.out
    assert "target: agy" in captured.out

    # 3. Status and Stop: active PID file
    # Start a dummy background process
    proc = subprocess.Popen(["sleep", "10"])
    pid = proc.pid

    pid_file.write_text(str(pid), encoding="utf-8")
    metadata_file.write_text(
        json.dumps(
            {
                "pid": pid,
                "schedule_id": 42,
                "target": "agy",
                "started_at": "2026-07-09T13:00:00Z",
                "log_path": "/tmp/test.log",
                "manifest_path": "/tmp/manifest.json",
            }
        ),
        encoding="utf-8",
    )

    # Check status of active pid
    exit_code = dailyfx_agent.main(["--status", "--pid-file", str(pid_file)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "status: running" in captured.out
    assert f"pid: {pid}" in captured.out

    # Stop active pid
    exit_code = dailyfx_agent.main(["--stop", "--pid-file", str(pid_file)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert f"daemon stopped: pid={pid}" in captured.out

    # Verify process was killed
    proc.wait(timeout=2.0)
    assert proc.returncode is not None

    # Verify files were cleaned up
    assert not pid_file.exists()
    assert not metadata_file.exists()


def test_agent_version_mcp_init(monkeypatch):
    # Mock _get_agent_version to return a unique custom version
    # Since _get_agent_version is not yet implemented, this mock is safe
    monkeypatch.setattr(dailyfx_agent, "_get_agent_version", lambda: "99.9.9")

    captured_params = []

    def fake_mcp_request(proc, request_id, method, params=None, **kwargs):
        if method == "initialize":
            captured_params.append(params)
            return {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "test-server", "version": "1.0"},
            }
        if method == "model/list":
            return {"models": []}
        return {}

    monkeypatch.setattr(dailyfx_agent, "_mcp_request", fake_mcp_request)

    class FakeProc:
        def __init__(self):
            self.stdin = StringIO()
            self.stdout = StringIO()
            self.stderr = StringIO()

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr(time, "time", lambda: 1000.0)

    try:
        dailyfx_agent._list_codex_models(timeout=5)
    except Exception:
        pass

    assert len(captured_params) == 1
    assert captured_params[0]["clientInfo"]["version"] == "99.9.9"


def test_doctor_command_scenarios(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    # Mock subprocess.run for docker compose config and doctor commands
    def fake_run(command, *args, **kwargs):
        cmd_str = " ".join(command) if isinstance(command, list) else str(command)
        if "docker compose config" in cmd_str:
            return CompletedProcess(command, 0, stdout="services:\n  api:\n", stderr="")
        if "curl" in cmd_str:
            return CompletedProcess(command, 0, stdout="ok", stderr="")
        if "dailyfx" in cmd_str:
            return CompletedProcess(command, 0, stdout="schedules", stderr="")
        if "agy" in cmd_str or "codex" in cmd_str:
            return CompletedProcess(command, 0, stdout="models", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Mock shutil.which to find executables
    import shutil

    monkeypatch.setattr(shutil, "which", lambda cmd: f"/usr/bin/{cmd}")

    # Mock Path.is_dir and os.access for recovery directories
    import os
    from pathlib import Path

    orig_is_dir = Path.is_dir

    def fake_is_dir(self):
        if "brain" in str(self) or "generated_images" in str(self):
            return True
        return orig_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", fake_is_dir)

    orig_access = os.access

    def fake_access(path, mode):
        if "brain" in str(path) or "generated_images" in str(path):
            return True
        return orig_access(path, mode)

    monkeypatch.setattr(os, "access", fake_access)

    # Invoke --doctor
    exit_code = dailyfx_agent.main(["--doctor"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Check" in captured.out
    assert "Status" in captured.out
    assert "Detail" in captured.out
    assert "stale_run_manifests" in captured.out


def test_augment_host_prompt_snapshot():
    original = "Generate a stylized photo of a cat."
    augmented = dailyfx_agent._augment_host_prompt(
        original_prompt=original,
        abs_image_path="/tmp/input.jpg",
        abs_manifest_path="/tmp/manifest.json",
        abs_output_path="/tmp/output.png",
        task_id="task-123",
    )
    assert original in augmented
    assert "/tmp/input.jpg" in augmented
    assert "/tmp/manifest.json" in augmented
    assert "/tmp/output.png" in augmented
    assert "task-123" in augmented
    assert "CRITICAL:" in augmented
    assert "[ ]" in augmented
    assert "metadata_source" in augmented


def test_lock_file_acquisition_and_cleanup(tmp_path, monkeypatch):
    import pytest

    locks_dir = tmp_path / "locks"
    monkeypatch.setattr(dailyfx_agent, "LOCKS_DIR", locks_dir)

    lock_file = locks_dir / "dailyfx-s1-agy.lock"

    # 1. Normal acquisition
    dailyfx_agent._acquire_lock(1, "agy")
    assert lock_file.exists()

    # 2. Re-acquisition under active process fails
    with pytest.raises(RuntimeError) as exc:
        dailyfx_agent._acquire_lock(1, "agy")
    assert "is already running" in str(exc.value)

    # 3. Re-acquisition under stale process overrides
    # Write a PID that doesn't exist
    import json

    lock_file.write_text(json.dumps({"pid": 999999, "started_at": "some-time"}), encoding="utf-8")
    dailyfx_agent._acquire_lock(1, "agy")
    assert lock_file.exists()

    # 4. Release lock
    dailyfx_agent._release_lock(1, "agy")
    assert not lock_file.exists()


def test_daemon_lock_update_records_child_pid(tmp_path, monkeypatch):
    locks_dir = tmp_path / "locks"
    monkeypatch.setattr(dailyfx_agent, "LOCKS_DIR", locks_dir)
    monkeypatch.setattr(dailyfx_agent.os, "getpid", lambda: 111)

    dailyfx_agent._acquire_lock(1, "agy")
    lock_file = locks_dir / "dailyfx-s1-agy.lock"

    dailyfx_agent._update_lock_for_daemon_child(1, "agy", 222)

    payload = json.loads(lock_file.read_text(encoding="utf-8"))
    assert payload["pid"] == 222
    assert payload["parent_pid"] == 111
    assert payload["child_pid"] == 222
    assert payload["owner_role"] == "daemon_child"


def test_repeat_manifest_paths(tmp_path, capsys):
    from pathlib import Path

    manifest_path = tmp_path / "custom.json"

    path_obj = Path(manifest_path)
    run2_path = path_obj.with_name(f"{path_obj.stem}-run2{path_obj.suffix}")
    assert run2_path.name == "custom-run2.json"


def test_diagnostics_arguments_parsing():
    parser = dailyfx_agent._build_parser()
    args = parser.parse_args(["--debug", "--json-status", "--schedule-id", "1", "--target", "agy"])
    assert args.debug is True
    assert args.json_status is True


def test_json_status_target_failure(tmp_path, monkeypatch, capsys):
    manifest = {
        "task_id": "cli-s1-abc123",
        "schedule_id": 1,
        "status": "PENDING_REVIEW",
        "title": "Initial",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "target": "agy",
    }
    backend_stdout = json.dumps(manifest)

    def fake_run(command, **kwargs):
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] in {"agy", "codex"}:
            return CompletedProcess(command, 1, stdout="", stderr="Fatal target error")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent, "LOCKS_DIR", tmp_path / "locks")

    exit_code = dailyfx_agent.main(
        ["--schedule-id", "1", "--target", "agy", "--project-dir", str(tmp_path), "--json-status"]
    )
    assert exit_code != 0
    captured = capsys.readouterr()
    status = json.loads(captured.out)
    assert status["stage"] == "target run"
    assert "Fatal target error" in status["error"]
    assert status["target"] == "agy"


def test_json_status_invalid_manifest(tmp_path, monkeypatch, capsys):
    def fake_run(command, **kwargs):
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout="corrupt json here{", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent, "LOCKS_DIR", tmp_path / "locks")

    exit_code = dailyfx_agent.main(
        ["--schedule-id", "1", "--target", "agy", "--project-dir", str(tmp_path), "--json-status"]
    )
    assert exit_code != 0
    captured = capsys.readouterr()
    status = json.loads(captured.out)
    assert status["stage"] == "manifest load"
    assert "JSONDecodeError" in status["error"] or "json" in status["error"].lower()


def test_json_status_missing_output(tmp_path, monkeypatch, capsys):
    manifest = {
        "task_id": "cli-s1-abc123",
        "schedule_id": 1,
        "status": "PENDING_REVIEW",
        "title": "Initial",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "target": "agy",
    }
    backend_stdout = json.dumps(manifest)

    def fake_run(command, **kwargs):
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if command and command[0] in {"agy", "codex"}:
            updated = {
                "title": "Updated Title",
                "summary": "Summary updated.",
                "tags": ["tag1", "tag2", "tag3"],
                "metadata_source": "host_agent_final_vision",
            }
            manifest_file = Path(command[-1])
            manifest_file.write_text(json.dumps(updated), encoding="utf-8")
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent, "LOCKS_DIR", tmp_path / "locks")
    monkeypatch.setattr(dailyfx_agent, "_find_latest_agy_image", lambda *args, **kwargs: None)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "agy",
            "--project-dir",
            str(tmp_path),
            "--json-status",
            "--agy-command-template",
            "exec --manifest {manifest_path}",
            "--debug",
        ]
    )
    assert exit_code != 0
    captured = capsys.readouterr()
    status = json.loads(captured.out)
    assert status["stage"] == "recovery"
    assert status["recovery_attempted"] is True
    assert "finished without creating" in status["error"]


def test_validate_output_image_rejects_invalid_image(tmp_path):
    import pytest

    invalid_image = tmp_path / "not-image.png"
    invalid_image.write_text("<html>not an image</html>", encoding="utf-8")

    with pytest.raises(ValueError, match="not a valid image"):
        dailyfx_agent._validate_output_image(invalid_image)


def test_successful_recovery_records_source_in_status_and_manifest(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    manifest_path = tmp_path / "run.json"
    generated_image = tmp_path / "generated-cli-s1-abc123.png"
    generated_image.write_bytes(_png_bytes())
    manifest = {
        "task_id": "cli-s1-abc123",
        "schedule_id": 1,
        "status": "PENDING_REVIEW",
        "generation_type": "ai_claymation",
        "title": "Initial",
        "summary": "Use the image.",
        "prompt": "Use the image.",
        "source_image_path": "/data/results/cli-s1-abc123.input.png",
        "output_path": "/data/results/cli-s1-abc123.png",
        "source_asset_id": "asset-1",
        "target": "agy",
        "config_json": {"existing": True},
        "tags": ["old1", "old2", "old3"],
    }
    backend_stdout = json.dumps(manifest)

    def fake_run(command, **kwargs):
        if "prepare-host" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
        if "finalize-host" in command:
            saved = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert saved["config_json"]["existing"] is True
            assert saved["config_json"]["recovered_from"] == str(generated_image.resolve())
            return CompletedProcess(command, 0, stdout="", stderr="")
        if command and command[0] in {"agy", "codex"}:
            manifest_path.write_text(
                json.dumps(
                    {
                        "title": "Updated Title",
                        "summary": "Updated final image summary.",
                        "tags": ["tag1", "tag2", "tag3"],
                        "metadata_source": "host_agent_final_vision",
                    }
                ),
                encoding="utf-8",
            )
            return CompletedProcess(command, 0, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dailyfx_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(dailyfx_agent.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dailyfx_agent, "LOCKS_DIR", tmp_path / "locks")
    monkeypatch.setattr(dailyfx_agent, "_find_latest_agy_image", lambda *args, **kwargs: generated_image)

    exit_code = dailyfx_agent.main(
        [
            "--schedule-id",
            "1",
            "--target",
            "agy",
            "--project-dir",
            str(tmp_path),
            "--manifest-path",
            str(manifest_path),
            "--agy-command-template",
            "exec --manifest {manifest_path}",
            "--json-status",
            "--keep-manifest",
        ]
    )

    assert exit_code == 0
    status = json.loads(capsys.readouterr().out)
    assert status["stage"] == "completed"
    assert status["recovery_attempted"] is True
    assert status["recovered_from"] == str(generated_image.resolve())
    assert status["output_image"]["width"] == 8
    assert status["output_image"]["height"] == 8

    artifact_dir = Path(status["artifact_dir"])
    assert (artifact_dir / "prompt.txt").exists()
    assert (artifact_dir / "manifest.before.json").exists()
    assert (artifact_dir / "manifest.after.json").exists()
    assert (artifact_dir / "target.log").exists()
    assert (artifact_dir / "status.json").exists()


def test_json_status_recovery_notes_do_not_pollute_stdout(tmp_path, monkeypatch, capsys):
    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    generated_image = generated_root / "render-cli-s1-abc123.png"
    generated_image.write_bytes(_png_bytes())

    recovered = dailyfx_agent._find_latest_image(
        start_time=time.time() - 1,
        generated_root=generated_root,
        task_id="cli-s1-abc123",
        notes_to_stderr=True,
    )

    captured = capsys.readouterr()
    assert recovered == generated_image
    assert captured.out == ""
    assert "Selected recovery image" in captured.err


def test_dailyfx_agent_accepts_schedule_target():
    from dailyfx_agent import _parse_args

    args = _parse_args(["--schedule-id", "1", "--target", "schedule"])
    assert args.target == "schedule"


def test_schedule_target_rejects_model_options(monkeypatch):
    from dailyfx_agent import main

    # test model option rejection
    exit_code = main(["--schedule-id", "1", "--target", "schedule", "--model", "some-model"])
    assert exit_code == 1

    # test list-models option rejection
    exit_code = main(["--target", "schedule", "--list-models"])
    assert exit_code == 1


def test_schedule_target_execution_short_circuits(monkeypatch):
    import json
    import subprocess

    from dailyfx_agent import main

    mock_manifest = {
        "task_id": "test-task",
        "status": "COMPLETED",
        "image_path": "/data/test_output.png",
        "prompt": "some prompt",
        "handoff_prompt": "some handoff prompt",
    }

    class MockCompletedProcess:
        def __init__(self, stdout, returncode=0):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    def mock_run(cmd, *args, **kwargs):
        return MockCompletedProcess(json.dumps(mock_manifest))

    monkeypatch.setattr(subprocess, "run", mock_run)

    # run main with schedule target
    exit_code = main(["--schedule-id", "1", "--target", "schedule"])
    assert exit_code == 0
