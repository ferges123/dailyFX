# Rate Limits Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Implement per-endpoint rate limits using `slowapi` to protect expensive backend calls and prevent resource exhaustion.

**Architecture:** Refactor `limiter` to a shared file `backend/app/limiter.py` to prevent circular imports. Apply the `@limiter.limit` decorator on targeted endpoints.

**Tech Stack:** FastAPI, slowapi.

---

### Task 1: Refactor limiter to shared module

**Files:**
- Create: `backend/app/limiter.py`
- Modify: `backend/app/main.py`

**Step 1: Write the failing test**
In `backend/tests/test_rate_limits.py` (create this file):
```python
def test_limiter_module_exists():
    from app.limiter import limiter
    assert limiter is not None
```

**Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_rate_limits.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Write minimal implementation**
- Create `backend/app/limiter.py` with the Limiter instance.
- Modify `backend/app/main.py` to import `limiter` from `app.limiter`.

**Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_rate_limits.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add backend/app/limiter.py backend/app/main.py
git commit -m "refactor: move Limiter instance to shared module"
```

---

### Task 2: Apply rate limits to route endpoints

**Files:**
- Modify: `backend/app/api/routes_studio.py`
- Modify: `backend/app/api/routes_schedules.py`
- Modify: `backend/app/api/routes_settings.py`

**Step 1: Write the failing test**
In `backend/tests/test_rate_limits.py`:
Write tests checking that sending multiple requests to `/api/studio/preview` triggers 429.

**Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_rate_limits.py -k test_studio_preview_rate_limit -v`
Expected: FAIL

**Step 3: Write minimal implementation**
- Import `limiter` in `routes_studio.py`, `routes_schedules.py`, and `routes_settings.py`.
- Add `@limiter.limit("5/minute")` to studio preview.
- Add `@limiter.limit("10/minute")` to manual run and settings routes.

**Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_rate_limits.py -k test_studio_preview_rate_limit -v`
Expected: PASS

**Step 5: Commit**
```bash
git add backend/app/api/routes_studio.py backend/app/api/routes_schedules.py backend/app/api/routes_settings.py
git commit -m "security: apply per-endpoint rate limits"
```

---

### Task 3: Complete verification and write full test coverage

**Files:**
- Modify: `backend/tests/test_rate_limits.py`

**Step 1: Write tests for settings and schedules run rate limits**
- Test that settings update triggers 429 after 10 requests.
- Test that manual run triggers 429 after 10 requests.

**Step 2: Run tests to verify they pass**
Run: `pytest backend/tests/test_rate_limits.py -v`
Expected: PASS

**Step 3: Run full backend test suite**
Run: `make backend-test`
Expected: PASS

**Step 4: Commit**
```bash
git add backend/tests/test_rate_limits.py
git commit -m "test: add comprehensive rate limiting unit tests"
```
