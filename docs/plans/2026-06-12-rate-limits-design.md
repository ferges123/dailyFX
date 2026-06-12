# Design Document: Per-Endpoint Rate Limits (Task 11)

## 1. Overview
This document specifies the design for adding per-endpoint rate limits using `slowapi` to protect expensive backend calls and prevent resource exhaustion or brute-force.

## 2. Refactoring Limiter Initialization
To prevent circular imports between `backend/app/main.py` and API route modules, we will move the `limiter` instance definition to a shared module:
* File: `backend/app/limiter.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
```

In `backend/app/main.py`, we will import `limiter` from `app.limiter`.

## 3. Targeted Route Limits
We will apply rate limits to the following endpoints:

### 3.1 Studio Preview
* Route: `POST /api/studio/preview` in `backend/app/api/routes_studio.py`
* Rate Limit: `5/minute` (5 generation previews per minute per IP)

### 3.2 Manual Scheduler Trigger
* Route: `POST /api/schedules/{schedule_id}/run-now` in `backend/app/api/routes_schedules.py`
* Rate Limit: `10/minute` (10 manual runs per minute per IP)

### 3.3 Settings Updates and Connection Tests
* Routes: in `backend/app/api/routes_settings.py`
  * `PUT /api/settings` -> `10/minute`
  * `POST /api/settings/test-immich` -> `10/minute`
  * `POST /api/settings/test-openai` -> `10/minute`
  * `POST /api/settings/test-gemini` -> `10/minute`
  * `POST /api/settings/test-openrouter` -> `10/minute`
  * `POST /api/settings/test-byteplus` -> `10/minute`
  * `POST /api/settings/test-xiaomi` -> `10/minute`
  * `POST /api/settings/test-local-ai` -> `10/minute`

## 4. Verification and Testing
* Write unit tests in `backend/tests/test_rate_limits.py`.
* Verify that calling rate-limited endpoints repeatedly returns `429 Too Many Requests` status code.
