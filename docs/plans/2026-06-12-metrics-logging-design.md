# Design Document: Metrics and Structured Logging (Task 15)

## 1. Overview
This document specifies the design for adding structured JSON logging and a Prometheus-compliant `/metrics` endpoint to the DailyFX backend. 

## 2. Structured JSON Logging
We will support toggling between human-readable text logging (default) and structured JSON logging (for production environments).

### 2.1 Configuration
Add to `AppSettings` in `backend/app/config.py`:
* `log_json: bool = Field(default=False, alias="LOG_JSON")`

Add to `.env.example`:
* `LOG_JSON=false`

### 2.2 Formatting
Create a custom logging Formatter in `backend/app/observability/logging.py` that formats log records into JSON strings containing:
* `timestamp` (ISO 8601 UTC)
* `level` (INFO, ERROR, etc.)
* `logger` (Name of the logger)
* `message` (Log message)
* `module` (Python module name)
* `function` (Function name)
* `line` (Line number)
* `exception` (Traceback if an exception occurred)

### 2.3 Setup on Startup
In `backend/app/main.py`, we will invoke a setup function that:
1. Replaces default log handlers if `LOG_JSON` is `True`.
2. Intercepts standard library logs and formats them to stdout.
3. Formats Uvicorn access/error logs to structured JSON.

---

## 3. Metrics Endpoint (`/metrics`)
Expose a public/protected `/metrics` endpoint returning Prometheus exposition format data.

### 3.1 Authentication
* If `APP_ACCESS_TOKEN` is set, enforce `require_auth` (Bearer authentication).
* If unset, allow unauthenticated access.
* This matches the rest of the application's API endpoints.

### 3.2 Database Queries Optimization
Instead of running heavy loads on every scrape, use SQLite index-backed group-by counts:
* **Active Tasks**: `SELECT status, COUNT(*) FROM generation_tasks GROUP BY status`
* **Historical Generations**: `SELECT status, COUNT(*) FROM generation_history GROUP BY status`

### 3.3 Exposition Format
Expose standard metrics:
* `dailyfx_app_info{version="0.2.14"} 1`
* `dailyfx_generation_task_status{status="..."} <count>`
* `dailyfx_generation_history_status{status="..."} <count>`
* `dailyfx_scheduler_heartbeat_age_seconds <seconds>`

We will implement this in `backend/app/api/routes_metrics.py`.

---

## 4. Verification and Testing
* Write unit tests in `backend/tests/test_metrics.py`.
* Verify that structured logging is configured correctly when `LOG_JSON` is toggled.
* Verify `/metrics` requires authentication only when `APP_ACCESS_TOKEN` is configured.
* Verify `/metrics` reports correct metrics.
