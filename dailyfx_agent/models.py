from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import time

from dailyfx_agent.config import is_testing
from dailyfx_agent.utils import _get_agent_version, _print_table


def _print_model_list_header(target: str) -> None:
    print(f"{target} models:")


def _parse_agy_model_line(line: str) -> dict[str, str] | None:
    text = line.strip()
    if not text:
        return None
    if text.lower().startswith("usage:") or text.lower().startswith("flags"):
        return None

    reasoning = "-"
    name = text
    if text.endswith(")") and "(" in text:
        open_index = text.rfind("(")
        candidate_reasoning = text[open_index + 1 : -1].strip()
        known_reasoning = {"low", "medium", "high", "xhigh", "minimal", "standard"}
        if candidate_reasoning and all(
            token.strip().lower() in known_reasoning
            for token in candidate_reasoning.split(",")
        ):
            reasoning = candidate_reasoning
            name = text[:open_index].strip()

    if not name:
        return None

    return {
        "id": name,
        "name": name,
        "reasoning": reasoning,
        "default": "-",
    }


def _get_agy_models(timeout: int = 15) -> list[str]:
    if is_testing():
        return ["gpt-5.5", "gemini-3.5-flash"]
    command = ["agy", "models"]
    try:
        run = subprocess.run(
            command, text=True, capture_output=True, check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return []
    if run.returncode != 0:
        return []
    models = []
    for line in run.stdout.splitlines():
        parsed = _parse_agy_model_line(line)
        if parsed and parsed.get("id"):
            models.append(parsed["id"])
    return models


class _JsonRpcReader:
    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()

    def put(self, line: str) -> None:
        self._queue.put(line)

    def read_message(self, timeout_seconds: float = 10.0) -> dict[str, object]:
        q = self._queue
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                line = q.get(timeout=remaining)
            except queue.Empty:
                continue
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        raise TimeoutError("Timed out waiting for Codex MCP response")


def _read_jsonrpc_message(
    reader: _JsonRpcReader, timeout_seconds: float = 10.0
) -> dict[str, object]:
    if not isinstance(reader, _JsonRpcReader):
        raise RuntimeError("Stream does not have a response queue attached")
    return reader.read_message(timeout_seconds)


def _mcp_request(
    proc: subprocess.Popen[str],
    request_id: int,
    method: str,
    params: dict[str, object] | None = None,
    *,
    deadline: float | None = None,
    reader: _JsonRpcReader | None = None,
) -> dict[str, object]:
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("Codex MCP server pipes are unavailable")
    if reader is None:
        raise RuntimeError("Codex MCP response reader is unavailable")
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    effective_deadline = deadline if deadline is not None else time.time() + 30.0
    while True:
        if time.time() >= effective_deadline:
            raise TimeoutError(f"MCP request {method!r} timed out")
        message = reader.read_message(
            timeout_seconds=max(0.01, min(10.0, effective_deadline - time.time()))
        )
        if message.get("id") == request_id:
            if "error" in message:
                raise RuntimeError(str(message["error"]))
            result = message.get("result")
            if isinstance(result, dict):
                return result
            raise RuntimeError("Codex MCP response missing result object")


def _get_codex_models(timeout: int = 15) -> list[str]:
    if is_testing():
        return ["gpt-5.5", "gemini-3.5-flash"]
    command = ["codex", "mcp-server"]

    deadline = time.time() + timeout
    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception as exc:
        sys.stderr.write(f"warning: failed to retrieve Codex models: {exc}\n")
        return []

    reader = _JsonRpcReader()

    def _reader() -> None:
        if proc.stdout is not None:
            for line in proc.stdout:
                reader.put(line)

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()

    try:
        _mcp_request(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "dailyfx-agent", "version": _get_agent_version()},
            },
            deadline=deadline,
            reader=reader,
        )
        if proc.stdin is None:
            return []
        proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        proc.stdin.flush()

        models: list[dict[str, object]] = []
        cursor: str | None = None
        request_id = 2
        while True:
            params: dict[str, object] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            result = _mcp_request(
                proc, request_id, "model/list", params,
                deadline=deadline, reader=reader,
            )
            request_id += 1
            batch = result.get("data")
            if isinstance(batch, list):
                for item in batch:
                    if isinstance(item, dict):
                        models.append(item)
            cursor = (
                result.get("nextCursor")
                if isinstance(result.get("nextCursor"), str)
                else None
            )
            if not cursor or time.time() >= deadline:
                break

        proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "exit"}) + "\n"
        )
        proc.stdin.flush()

        res = []
        for model in models:
            model_id = str(model.get("model") or model.get("id") or "")
            if model_id:
                res.append(model_id)
        return res
    except Exception as exc:
        sys.stderr.write(f"warning: failed to retrieve Codex models: {exc}\n")
        return []
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _list_agy_models(timeout: int = 30) -> int:
    command = ["agy", "models"]
    try:
        run = subprocess.run(
            command, text=True, capture_output=True, check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"agy models timed out after {timeout}s\n")
        return 124
    if run.returncode != 0:
        if run.stderr:
            sys.stderr.write(run.stderr)
        elif run.stdout:
            sys.stderr.write(run.stdout)
        return run.returncode or 1
    rows = []
    for line in run.stdout.splitlines():
        parsed = _parse_agy_model_line(line)
        if parsed:
            rows.append(parsed)
    if not rows:
        print("No models found")
        return 0
    print(
        "Note: agy does not expose a separate model id/default flag in this build; ID shows the selectable label."
    )
    _print_table(
        rows,
        [
            ("id", "ID"),
            ("name", "NAME"),
            ("reasoning", "REASONING"),
            ("default", "DEFAULT"),
        ],
    )
    return 0


def _list_codex_current_model(timeout: int = 15) -> dict[str, str] | None:
    import re

    try:
        run = subprocess.run(
            ["codex", "doctor"],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None
    if run.returncode != 0:
        return None
    match = re.search(
        r"^\s*model\s+([^\s·]+)\s+·\s+([^\s]+)\s*$", run.stdout, re.MULTILINE
    )
    if not match:
        return None
    model_id, provider = match.groups()
    return {
        "id": model_id,
        "name": model_id,
        "provider": provider,
        "reasoning": "-",
        "default": "yes",
    }


def _list_codex_models(timeout: int = 60) -> int:
    command = ["codex", "mcp-server"]
    deadline = time.time() + timeout
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    reader = _JsonRpcReader()

    def _reader() -> None:
        if proc.stdout is not None:
            for line in proc.stdout:
                reader.put(line)

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()

    try:
        _mcp_request(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "dailyfx-agent", "version": _get_agent_version()},
            },
            deadline=deadline,
            reader=reader,
        )
        if proc.stdin is None:
            raise RuntimeError("Codex MCP server stdin is unavailable")
        proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        proc.stdin.flush()

        models: list[dict[str, object]] = []
        cursor: str | None = None
        request_id = 2
        while True:
            params: dict[str, object] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            result = _mcp_request(
                proc, request_id, "model/list", params,
                deadline=deadline, reader=reader,
            )
            request_id += 1
            batch = result.get("data")
            if isinstance(batch, list):
                for item in batch:
                    if isinstance(item, dict):
                        models.append(item)
            cursor = (
                result.get("nextCursor")
                if isinstance(result.get("nextCursor"), str)
                else None
            )
            if not cursor:
                break

        if not models:
            print("No models found")
            return 0

        rows = []
        for model in models:
            model_id = str(model.get("model") or model.get("id") or "")
            display_name = str(model.get("displayName") or model_id)
            is_default = "yes" if model.get("isDefault") else "no"
            efforts = model.get("supportedReasoningEfforts") or []
            if isinstance(efforts, list):
                reasoning = ", ".join(
                    str(item.get("reasoningEffort"))
                    for item in efforts
                    if isinstance(item, dict) and item.get("reasoningEffort")
                )
            else:
                reasoning = ""
            rows.append(
                {
                    "id": model_id,
                    "name": display_name,
                    "reasoning": reasoning,
                    "default": is_default,
                }
            )
        _print_table(
            rows,
            [
                ("id", "ID"),
                ("name", "NAME"),
                ("reasoning", "REASONING"),
                ("default", "DEFAULT"),
            ],
        )
        return 0
    except Exception as exc:
        fallback = _list_codex_current_model()
        if fallback is not None:
            print(
                "Note: codex mcp-server did not expose model/list in this build; showing the current configured model instead."
            )
            _print_table(
                [fallback],
                [
                    ("id", "ID"),
                    ("name", "NAME"),
                    ("provider", "PROVIDER"),
                    ("reasoning", "REASONING"),
                    ("default", "DEFAULT"),
                ],
            )
            return 0
        sys.stderr.write(f"{exc}\n")
        return 1
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
