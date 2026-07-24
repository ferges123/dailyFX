# DailyFX Host Agent (`dailyfx-agent`)

The `dailyfx-agent` is a host-side orchestrator script written in Python. It acts as a bridge between the DailyFX backend running inside Docker containers and local host-side AI agent environments (specifically Gemini/Antigravity and OpenAI/Codex).

It prepares scheduled generation runs, invokes local AI agents with visual context, validates metadata, and submits finalized results back to the backend.

---

## Architecture & Workflow

The orchestrator operates at the boundary between your local system (host) and Docker containers. This allows it to leverage host-running LLM and vision agents that require local resources or configuration, while storing data and scheduling runs within Docker.

```mermaid
sequenceDiagram
    autonumber
    participant Host CLI as dailyfx-agent
    participant Docker Backend as DailyFX API
    participant AI Agent as Host AI (agy / codex)

    Host CLI->>Docker Backend: 1. Prepare run (prepare-host CLI command)
    Docker Backend-->>Host CLI: 2. Return run manifest (JSON payload)
    Host CLI->>Host CLI: 3. Augment prompt with Source & Final Vision instructions
    Host CLI->>AI Agent: 4. Execute target with prompt on stdin
    Note over AI Agent: Source Vision: Analyze input image<br/>Render: Apply effect & save<br/>Final Vision: Analyze output image<br/>Update: manifest.json (title, summary, tags)
    AI Agent-->>Host CLI: 5. Completion & Updated Manifest
    Note over Host CLI: If output image is missing,<br/>recover from agent brain directory
    Host CLI->>Host CLI: 6. Validate manifest changes
    Host CLI->>Docker Backend: 7. Finalize run (finalize-host CLI command)
```

1. **Prepare Run**: The host agent queries the Docker container to prepare a scheduled generation. The backend prepares the database entry and replies with a JSON manifest.
2. **Setup Manifest**: The manifest is saved temporarily on the host and copied to a directory shared with the container.
3. **Execute AI Tool**: The script runs the local tool (`agy` or `codex`) via shell. It streams progress labels from the container's generation trace to a visual spinner.
4. **Agent Action**: The local agent receives the prompt (injected with vision tasks) on standard input, processes the image, saves the result, and updates the local manifest file.
5. **Verify & Recover**: The script checks if the image exists. If not, it recovers the image from known agent directories. It then validates that the agent successfully updated the title, summary, and tags.
6. **Finalize**: The script triggers the finalization CLI command inside the container to upload the image and store the metadata.

---

## CLI Reference

Execute the agent from the project root:

```bash
./dailyfx-agent [OPTIONS]
```

### Options

| Flag | Type | Default | Description |
|---|---|---|---|
| `-s, --schedule-id` | `int` | `None` | Schedule ID to execute. Required unless `--list-schedules` is used. |
| `-t, --target` | `str` | `None` | Target tool to call (`agy` or `codex`). Required unless listing schedules. |
| `-m, --model` | `str` | `None` | Specific model to use for the selected target. |
| `-l, --list-schedules` | `flag` | `False` | List available schedule IDs and names from backend database, then exit. |
| `--list-models` | `flag` | `False` | List available models for the selected target, then exit. |
| `--compose-file` | `str` | `"docker-compose.yml"` | Path to the docker-compose YAML file. |
| `--project-dir` | `str` | `"."` | Directory containing the compose file. |
| `--service` | `str` | `"api"` | Name of the Docker Compose service running DailyFX. |
| `--manifest-path` | `str` | `None` | Optional path for the temporary manifest JSON. |
| `--keep-manifest` | `flag` | `False` | Prevent deletion of temporary manifest files after execution. |
| `--dry-run` | `flag` | `False` | Print compose and host commands without executing them. |
| `-v, --verbose` | `flag` | `False` | Print the loaded manifest payload before calling the target. |
| `--agy-command-template` | `str` | `"--print {prompt}"` | Command template for `agy`. Supports `{image_path}`, `{output_path}`, `{manifest_path}`, and `{prompt}`. |
| `--codex-command-template`| `str` | `"exec --image {image_path} -"`| Command template for `codex`. Supports `{image_path}`, `{output_path}`, and `{manifest_path}`. |
| `--timeout` | `int` | `600` | Timeout in seconds for the target tool execution. |
| `-x, --repeat` | `int` | `1` | Number of times to repeat the execution task. |
| `--strict-recovery/--no-strict-recovery` | `bool` | `True` | Require a recovered image to match the task ID; disable only for legacy fallback behavior. |
| `-d, --daemon` | `flag` | `False` | Run in background (detached daemon mode). Writes PID and exits immediately. |
| `--pid-file` | `str` | `None` | Path to write the daemon PID file. Defaults to `data/dailyfx-agent-{target}.pid`. |
| `--status` | `flag` | `False` | Check the status of the daemon process. |
| `--stop` | `flag` | `False` | Stop the running daemon process. |
| `--doctor` | `flag` | `False` | Run environment diagnostics and verify dailyfx-agent setup. |
| `--debug` | `flag` | `False` | Enable print of detailed error backtraces and context information. |
| `--json-status` | `flag` | `False` | Output execution diagnostics and status formatted as JSON on exit. |

---

## The Metadata & Vision Pipeline

The orchestrator enforces a dual-vision analysis pipeline when dispatching tasks to host-side agents:

### 1. Source Vision (Context Analysis)
The agent is instructed to open and analyze the source image (`source_image_path`) on the host to understand:
- The context, subjects, and people present.
- The lighting, mood, and original setting.

### 2. Final Vision (Validation & Description)
After applying the generative effect and saving the output image, the agent must examine the final image to:
- Evaluate the aesthetic results.
- Ensure the output is correct.

### Prompt Augmentation
The script automatically appends the following instructions to the manifest prompt sent to the host agent:

```
CRITICAL: As the AI agent running on the host, you MUST perform both:
1. Source Vision: Analyze the input image (source photo) at '<absolute_input_path>' for context, theme, and people.
2. Final Vision: Analyze the final generated image (after generating/saving it) for what actually appears in it.
Use these vision steps to generate:
- A high-quality title (a short, creative 3-5 word title)
- A summary (one concise sentence describing the final image)
- A list of 3-6 descriptive tags (keywords) summarizing the image content
You MUST write/update these values in the local JSON manifest file at '<absolute_manifest_path>' under the 'title', 'summary', 'tags', and 'metadata_source' keys before exiting.
Set 'metadata_source' to 'host_agent_final_vision'.
The final output image path is '<absolute_output_path>'.
```

### Manifest Verification
Before finalizing, `dailyfx-agent` validates the updated manifest file. It raises an error and halts execution if:
- `title` is empty.
- `summary` is empty.
- `tags` is not a list, contains invalid values, or its size is not between **3 and 6** items.
- `metadata_source` is not explicitly set to `"host_agent_final_vision"`.
- The updated values are identical to the original values (verifies that the agent did not skip the step).

The host agent may write a partial metadata-only manifest update. In that case, `dailyfx-agent` merges the update over the original backend manifest before finalization, preserving technical fields such as `task_id`, `schedule_id`, `target`, `output_path`, and `config_json`.

---

## Automatic Image Recovery (Fallback Search)

If the local agent exits successfully (`returncode 0`) but the target output file does not exist at `output_path`, `dailyfx-agent` attempts to recover the image from the agent's internal directories.

### Recovery Directories
Depending on the selected target, the script checks:
- **`codex`**: `~/.codex/generated_images`
- **`agy`**: `~/.gemini/antigravity-cli/brain`

### Selection Algorithm
1. The script lists files in the directory.
2. It filters out files that contain words like `"input"` or `"original"`.
3. It filters for image extensions: `.png`, `.webp`, `.jpg`, `.jpeg`.
4. It considers image files created/modified after the target tool's launch timestamp with a 10-second safety buffer. Directory discovery uses a separate 5-minute buffer so slow agents can finish inside older session folders.
5. It prefers candidates whose filename or parent directory contains the current `task_id`.
6. If no task-specific candidate exists, it falls back to the **most recently modified** image and prints a warning.
7. The script copies this recovered image to the final `output_path`, records the source path as `recovered_from` in the JSON status payload and manifest `config_json`, then proceeds to finalize. If no candidate is found, it reports a missing output file error.

---

## Process & Log Management

### Active Visual Feedback
When running interactively (non-daemon mode), the script parses the backend's `task_trace` to display a command-line spinner on `stderr`. The spinner maps internal stages to user-friendly labels:
- `selecting_asset`, `searching_assets` -> `[search]`
- `running`, `planning` -> `[plan]`
- `applying_effect`, `rendering` -> `[render]`
- `analyzing_image`, `embedding_metadata` -> `[analyze]`
- `saving_result`, `host_finalizing` -> `[save]`
- `succeeded`, `completed` -> `[done]`
- `failed` -> `[fail]`

### Log files & Rotation
Target tool output is not printed directly to stdout. Stdin/stderr logs of the executed target command are captured and written to:
`data/logs/agent/dailyfx-agent-{task_id}-{target}-{timestamp}.log`

The script automatically retains only the **5 most recent logs** for each task runner, deleting older log files to conserve disk space.

### Per-task Artifacts
For each prepared task, `dailyfx-agent` also writes a compact diagnostic bundle under:
`data/logs/agent/tasks/{task_id}/`

The bundle can include:
- `manifest.before.json`: the backend manifest before the host tool runs.
- `prompt.txt`: the final augmented prompt sent to the host tool.
- `target.log`: a copy of the captured host tool stdout/stderr log.
- `manifest.after.json`: the normalized manifest after metadata validation and optional recovery metadata.
- `status.json`: the final structured execution status.

These files are intended for debugging failed or surprising host runs without re-running the task.

### Output Image Validation
Before finalization, the wrapper validates the output file. It must:
- exist at the resolved `output_path`;
- contain at least one byte;
- be readable by Pillow as an image;
- have non-zero width and height.

If validation fails, finalization is skipped and the run stops at the `output validation` stage.

### Daemon Mode
For background execution, specify the `-d` or `--daemon` flag.
- The process forks using `os.fork()`.
- The parent log of the daemon process is redirected to a dedicated log file under `data/logs/agent/` instead of `/dev/null`.
- The child process's PID is printed to the shell and saved to a target PID file (e.g. `data/dailyfx-agent-agy.pid`).
- A JSON metadata file is created alongside it at `{pid_file}.json`, recording: `pid`, `schedule_id`, `target`, `started_at`, `log_path`, and `manifest_path`.
- The run lock records `parent_pid`, `child_pid`, and `owner_role` so daemon runs are associated with the child process rather than the short-lived parent.
- The spinner is automatically bypassed in daemon mode.
- The PID and metadata files are cleaned up when execution finishes.
- There is at most one worker per host target (`agy` and `codex`). A second invocation for an active target is persisted in `data/agent-queues/<target>/pending/` and returns `queued` without starting another target process. The worker drains pending jobs in FIFO order. Target PID files therefore use `data/dailyfx-agent-agy.pid` and `data/dailyfx-agent-codex.pid`.

### Process Status and Stopping
You can manage the running daemon process using these flags:
- `--status`: Reads the PID and JSON metadata file to check if the daemon process is running. Prints process information (running, stopped due to missing file, or stopped with stale files) along with metadata details.
- `--stop`: Reads the PID, terminates the daemon process (using SIGTERM, followed by SIGKILL if it does not exit within 2 seconds), and cleans up the PID and metadata files.

## Versioning

The `dailyfx-agent` resolves its version dynamically to stay aligned with the backend application:
1. It tries to dynamically import the backend package version (`app.version.APP_VERSION`).
2. If the import fails, it parses the `pyproject.toml` configuration file under the `backend/` directory.
3. In case both fail, it falls back to using `importlib.metadata` or the backend-aligned default version identifier (`"0.15.0"`).

This resolved version is used during Codex MCP initialization as the client version (under `clientInfo.version`).

---

## Examples

### 1. Show Schedules
Check the schedules configured in the database:
```bash
./dailyfx-agent --list-schedules
```

### 2. Check Available AI Models
Query models available on the host:
```bash
./dailyfx-agent --list-models --target agy
./dailyfx-agent --list-models --target codex
```

### 3. Run a Scheduled Task
Run schedule `2` using Gemini (`agy`):
```bash
./dailyfx-agent --schedule-id 2 --target agy
```

Run schedule `2` in the background (detached daemon):
```bash
./dailyfx-agent --schedule-id 2 --target agy --daemon
```

### 4. Custom Command Templates
To configure Codex to accept image data on standard input or wrap command execution:
```bash
./dailyfx-agent \
  --schedule-id 1 \
  --target codex \
  --model gpt-4o \
  --codex-command-template 'exec --image {image_path} -'
```

> **Warning**: The orchestrator quotes substituted paths automatically. Do **not** wrap `{image_path}`, `{manifest_path}`, or `{output_path}` in quotes in your templates.

### 5. Error Diagnostics & JSON Status
To output structured execution summaries on exit (both on success or failure), use `--json-status`:
```bash
./dailyfx-agent --schedule-id 1 --target agy --json-status
```
The stdout will print a serialized JSON object:
```json
{
  "task_id": "cli-s1-abc123",
  "schedule_id": 1,
  "target": "agy",
  "model": null,
  "stage": "completed",
  "manifest_path": "/opt/dailyFX/data/dailyfx-run-abc.json",
  "source_image_path": "/opt/dailyFX/data/results/cli-s1-abc123.input.png",
  "output_path": "/opt/dailyFX/data/results/cli-s1-abc123.png",
  "target_log_path": "/opt/dailyFX/data/logs/agent/dailyfx-agent-cli-s1-abc123-agy-20260709-130000.log",
  "recovery_attempted": false,
  "recovered_from": null,
  "artifact_dir": "/opt/dailyFX/data/logs/agent/tasks/cli-s1-abc123",
  "output_image": {
    "path": "/opt/dailyFX/data/results/cli-s1-abc123.png",
    "size_bytes": 123456,
    "width": 1024,
    "height": 1024,
    "format": "PNG"
  },
  "error": null
}
```
Available stages: `prepare`, `manifest load`, `target run`, `metadata validation`, `recovery`, `output validation`, `finalize`, `completed`.
When `--json-status` is enabled, stdout is reserved for this JSON object. Warnings and recovery notes are written to stderr.
If detailed error logs and backtraces are needed, add `--debug` to print them to `stderr`.
