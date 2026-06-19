# People Filter Limit Increase Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Change the maximum number of people returned in the filter presets settings from 20 to 33.

**Architecture:** Update the slice limit `[:20]` to `[:33]` in the backend Immich client `list_people` function, add unit tests, and bump the version string across package configuration files.

**Tech Stack:** FastAPI, Pydantic, pytest, React + TypeScript (Vite)

---

### Task 1: Add a test asserting the 33-people limit

**Files:**
- Modify: `backend/tests/test_immich_client.py`

**Step 1: Write the failing test**
Append the following test to the end of `backend/tests/test_immich_client.py`:

```python
def test_list_people_limits_to_33(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock a list of 40 people returned from the Immich API
    mock_people = [
        {"id": f"person-{i}", "name": f"Person {i}", "isHidden": False}
        for i in range(1, 41)
    ]
    payloads = iter([{"people": mock_people, "hasNextPage": False}])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/people":
            return httpx.Response(200, json=next(payloads))
        # Statistics for each person showing positive asset counts so they are not hidden/excluded
        return httpx.Response(200, json={"assets": 1})

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    people = asyncio.run(ImmichClient("https://photos.example.com", "secret-key").list_people())

    # We expect exactly 33 people to be returned after the change
    assert len(people) == 33
```

**Step 2: Run test to verify it fails**
Run: `make backend-test` (or `pytest backend/tests/test_immich_client.py -k test_list_people_limits_to_33`)
Expected: FAIL with `AssertionError: assert 20 == 33`

---

### Task 2: Update Immich client to return up to 33 people

**Files:**
- Modify: `backend/app/immich/client.py`

**Step 1: Write minimal implementation**
In `backend/app/immich/client.py` around line 668, update:
```python
            enriched.sort(key=lambda p: (-p.asset_count, p.name.lower()))
            return enriched[:33]
```

**Step 2: Run test to verify it passes**
Run: `cd backend && .venv/bin/pytest tests/test_immich_client.py -k test_list_people_limits_to_33 -v`
Expected: PASS

**Step 3: Run the full backend test suite to verify no regressions**
Run: `make backend-test`
Expected: PASS (all 352 tests pass)

**Step 4: Commit**
Run: `git add backend/app/immich/client.py backend/tests/test_immich_client.py && git commit -m "backend: increase people filter limit to 33 and add test"`

---

### Task 3: Bump application version to 0.3.20

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/version.ts`

**Step 1: Modify files**
Update `"version": "0.3.19"` to `"version": "0.3.20"` in `frontend/package.json` and `frontend/package-lock.json`.
Update `export const APP_VERSION = '0.3.19';` to `export const APP_VERSION = '0.3.20';` in `frontend/src/version.ts`.

**Step 2: Verify the frontend builds successfully**
Run: `cd frontend && npm run build`
Expected: Successful production build without errors.

**Step 3: Run frontend tests to ensure no regressions**
Run: `cd frontend && npm test`
Expected: PASS

**Step 4: Commit**
Run: `git add frontend/package.json frontend/package-lock.json frontend/src/version.ts && git commit -m "frontend: bump version to 0.3.20"`
