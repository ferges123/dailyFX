from __future__ import annotations

import json
import os
import sys
import time
from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dailyfx_agent  # noqa: E402


def _seed_agy_generated_image(tmp_path, filename="desert_diorama_123.jpg"):
    generated_root = tmp_path / ".gemini" / "antigravity-cli" / "brain" / "session-1"
    generated_root.mkdir(parents=True)
    image_path = generated_root / filename
    image_path.write_bytes(b"agy image bytes")
    os.utime(image_path, (time.time() + 100, time.time() + 100))
    return image_path


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
    assert (tmp_path / "run.json").read_text(encoding="utf-8") == backend_stdout
    assert "image provider: agy" in captured.out
    assert "done: ./data/results/cli-s1-abc123.png" in captured.out


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
    }
    backend_stdout = json.dumps(manifest)
    calls: list[list[str]] = []
    _seed_agy_generated_image(tmp_path)

    def fake_run(command, **kwargs):
        calls.append(command)
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
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
    }
    backend_stdout = json.dumps(manifest)
    generated_root = tmp_path / ".codex" / "generated_images" / "session-1"
    generated_root.mkdir(parents=True)
    codex_image = generated_root / "ig_test.png"
    codex_image.write_bytes(b"codex image bytes")
    os.utime(codex_image, (time.time() + 100, time.time() + 100))
    calls: list[list[str]] = []
    inputs: list[str | None] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        inputs.append(kwargs.get("input"))
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
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
    }
    backend_stdout = json.dumps(manifest)
    generated_root = tmp_path / ".codex" / "generated_images" / "session-1"
    generated_root.mkdir(parents=True)
    codex_image = generated_root / "ig_test.png"
    codex_image.write_bytes(b"codex image bytes")
    os.utime(codex_image, (time.time() + 100, time.time() + 100))
    calls: list[list[str]] = []
    inputs: list[str | None] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        inputs.append(kwargs.get("input"))
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
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
    assert output_path.read_bytes() == b"codex image bytes"


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
    agy_image.write_bytes(b"agy image bytes")
    os.utime(agy_image, (time.time() + 100, time.time() + 100))
    calls: list[list[str]] = []
    inputs: list[str | None] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        inputs.append(kwargs.get("input"))
        if "dailyfx" in command:
            return CompletedProcess(command, 0, stdout=backend_stdout, stderr="")
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
    assert output_path.read_bytes() == b"agy image bytes"


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

    result, log_path = dailyfx_agent._run_target_with_spinner(
        ["true"], prompt="", task_id="test", labels=["label1"]
    )

    captured = stderr_mock.getvalue()
    assert "\033[K" in captured
    assert "\r\033[K" in captured

