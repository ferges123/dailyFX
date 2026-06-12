# Metrics and Structured Logging Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Add structured JSON logging behind a configuration flag `LOG_JSON` and expose a secure, lightweight `/metrics` Prometheus endpoint.

**Architecture:** A custom JSON logging formatter is configured at startup if enabled. The `/metrics` endpoint executes efficient index-backed database count queries and exposes standard Prometheus exposition text.

**Tech Stack:** FastAPI, SQLAlchemy, Python Logging standard library, Pytest.

---

### Task 1: Add configuration settings

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example`

**Step 1: Write the failing test**
In `backend/tests/test_metrics_and_logging.py` (we will create this file):
```python
def test_settings_has_log_json_and_defaults_to_false():
    from app.config import AppSettings
    # We will verify settings default behavior
```

**Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_metrics_and_logging.py -v`
Expected: FAIL (File/Test module not found or fields missing)

**Step 3: Write minimal implementation**
- Add `log_json: bool = Field(default=False, alias="LOG_JSON")` to `AppSettings` in `backend/app/config.py`.
- Add `# LOG_JSON=false` or similar under `# Optional:` in `.env.example`.

**Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_metrics_and_logging.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add backend/app/config.py .env.example
git commit -m "config: add LOG_JSON setting"
```

---

### Task 2: Implement structured JSON formatter and setup

**Files:**
- Create: `backend/app/observability/logging.py`

**Step 1: Write the failing test**
In `backend/tests/test_metrics_and_logging.py`:
```python
def test_json_formatter_outputs_valid_json():
    from app.observability.logging import JSONFormatter
    import logging
    # Format a record and check if it has JSON keys
```

**Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_metrics_and_logging.py -k test_json_formatter_outputs_valid_json -v`
Expected: FAIL (No module app.observability.logging)

**Step 3: Write minimal implementation**
Implement `JSONFormatter` and `setup_logging` in `backend/app/observability/logging.py`.
- Formatter extracts `asctime`, `levelname`, `name`, `message`, `module`, `funcName`, `lineno`.
- Formatter prints JSON with keys: `timestamp`, `level`, `logger`, `message`, `module`, `function`, `line`.
- If record has exception, format and add as `exception` key.

**Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_metrics_and_logging.py -k test_json_formatter_outputs_valid_json -v`
Expected: PASS

**Step 5: Commit**
```bash
git add backend/app/observability/logging.py
git commit -m "observability: implement JSONFormatter and logging setup"
```

---

### Task 3: Hook logging setup to main app startup

**Files:**
- Modify: `backend/app/main.py`

**Step 1: Write the failing test**
In `backend/tests/test_metrics_and_logging.py`:
```python
def test_app_startup_configures_logging(monkeypatch):
    # Test that setup_logging is called with the config value
```

**Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_metrics_and_logging.py -k test_app_startup_configures_logging -v`
Expected: FAIL

**Step 3: Write minimal implementation**
Import and run `setup_logging` in `backend/app/main.py`.

**Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_metrics_and_logging.py -k test_app_startup_configures_logging -v`
Expected: PASS

**Step 5: Commit**
```bash
git add backend/app/main.py
git commit -m "observability: hook setup_logging into main.py startup"
```

---

### Task 4: Expose `/metrics` route

**Files:**
- Create: `backend/app/api/routes_metrics.py`

**Step 1: Write the failing test**
In `backend/tests/test_metrics_and_logging.py`:
```python
def test_metrics_endpoint_returns_prometheus_format():
    # Use TestClient to query /metrics
```

**Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_metrics_and_logging.py -k test_metrics_endpoint_returns_prometheus_format -v`
Expected: FAIL (404 Not Found)

**Step 3: Write minimal implementation**
- Create `backend/app/api/routes_metrics.py` with standard Prometheus route at `/metrics`.
- Expose status metrics by querying counts from `GenerationTaskModel` and `GenerationHistoryModel` grouped by status.
- Expose app version and scheduler heartbeat age.

**Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_metrics_and_logging.py -k test_metrics_endpoint_returns_prometheus_format -v`
Expected: PASS

**Step 5: Commit**
```bash
git add backend/app/api/routes_metrics.py
git commit -m "api: implement Prometheus metrics endpoint"
```

---

### Task 5: Register routes_metrics in main.py

**Files:**
- Modify: `backend/app/main.py`

**Step 1: Write the failing test**
Test `/metrics` endpoint behavior directly from the FastAPI `app` object.

**Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_metrics_and_logging.py -k test_metrics_endpoint_returns_prometheus_format -v`
Expected: FAIL if not registered in main.py.

**Step 3: Write minimal implementation**
Import `metrics_router` and `app.include_router(metrics_router)` in `backend/app/main.py`.

**Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_metrics_and_logging.py -k test_metrics_endpoint_returns_prometheus_format -v`
Expected: PASS

**Step 5: Commit**
```bash
git add backend/app/main.py
git commit -m "api: register metrics router in main application"
```

---

### Task 6: Add full verification tests (metrics auth and logic)

**Files:**
- Modify: `backend/tests/test_metrics_and_logging.py`

**Step 1: Write tests for authentication behavior**
- Test `/metrics` returns 401 when `APP_ACCESS_TOKEN` is configured but missing in headers.
- Test `/metrics` returns 200 when `APP_ACCESS_TOKEN` is configured and correct token is provided.
- Test `/metrics` returns 200 when `APP_ACCESS_TOKEN` is empty/unset.

**Step 2: Run test to verify it fails**
Expected: FAIL (until implementation is complete and secure)

**Step 3: Write minimal implementation / verify implementation**
Ensure the `/metrics` endpoint is protected via `Depends(require_auth)`.

**Step 4: Run all tests in the project**
Run: `make backend-test`
Expected: PASS (298 + new tests)

**Step 5: Commit**
```bash
git add backend/tests/test_metrics_and_logging.py
git commit -m "test: add comprehensive unit tests for metrics and logging"
```
