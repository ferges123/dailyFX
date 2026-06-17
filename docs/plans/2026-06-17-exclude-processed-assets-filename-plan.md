# Exclude dailyFX Processed Photos from AI/Random Selection Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Exclude already dailyFX-processed photos from being selected in automatic/random dailyFX cycles based on their filename.

**Architecture:** Filter the candidate assets in `_prepare_page_items_for_module` to exclude items whose `original_file_name` contains `"dailyfx"` (case-insensitive), unless they are manually selected via `selected_asset_ids`.

**Tech Stack:** Python, pytest, Node.js

---

### Task 1: Write and Verify Failing Unit Tests

**Files:**
- Modify: `backend/tests/test_engine.py`

**Step 1: Write the failing tests**

Add these two test cases to the end of `backend/tests/test_engine.py`:

```python
def test_prepare_page_items_excludes_dailyfx_assets_automatically():
    from app.services.generation.pipeline.assets import _prepare_page_items_for_module
    
    # 4 assets, 2 of which are processed dailyFX assets
    assets = [
        _make_fake_asset("asset-1", filename="clean_photo.jpg"),
        _make_fake_asset("asset-2", filename="photo_dailyFX.jpg"),
        _make_fake_asset("asset-3", filename="another_clean.png"),
        _make_fake_asset("asset-4", filename="my_dailyfx_processed.jpeg"),
    ]
    page = _make_fake_page(assets)
    module = SimpleNamespace(source_asset_count=1, name="instafilter")

    selected = _prepare_page_items_for_module(
        page=page,
        module=module,
        selected_asset_ids=None,
        ai_photo_selection_enabled=True,
        task_id="task-automatic-filter",
        _task_update=lambda **kwargs: None,
    )

    # Only asset-1 and asset-3 should be selected since others contain 'dailyfx' case-insensitively
    assert selected is not None
    assert [asset.id for asset in selected] == ["asset-1", "asset-3"]


def test_prepare_page_items_retains_dailyfx_assets_manually():
    from app.services.generation.pipeline.assets import _prepare_page_items_for_module
    
    assets = [
        _make_fake_asset("asset-1", filename="clean_photo.jpg"),
        _make_fake_asset("asset-2", filename="photo_dailyFX.jpg"),
    ]
    page = _make_fake_page(assets)
    module = SimpleNamespace(source_asset_count=1, name="instafilter")

    # Manually select asset-2 (even though it contains dailyFX in its name)
    selected = _prepare_page_items_for_module(
        page=page,
        module=module,
        selected_asset_ids=["asset-2"],
        ai_photo_selection_enabled=True,
        task_id="task-manual-override",
        _task_update=lambda **kwargs: None,
    )

    assert selected is not None
    assert [asset.id for asset in selected] == ["asset-2"]
```

*Note: In `test_engine.py`, we need to make sure `_make_fake_asset` supports the `original_file_name` parameter, or we patch the attribute. Let's look at `_make_fake_asset` signature in `test_engine.py` to see if it supports `original_file_name`.*

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_engine.py -k test_prepare_page_items_ -v`
Expected: FAIL (with assertions showing all 4 assets selected instead of only 2).

**Step 3: Commit**

```bash
git add backend/tests/test_engine.py
git commit -m "test: add tests for filename-based processed asset filtering"
```

---

### Task 2: Implement Asset Exclusion Logic in assets.py

**Files:**
- Modify: `backend/app/services/generation/pipeline/assets.py`

**Step 1: Write minimal implementation**

Modify `_prepare_page_items_for_module` in `backend/app/services/generation/pipeline/assets.py` to perform the filtering:

```python
    page_items = _select_page_items(
        page=page, selected_asset_ids=selected_asset_ids, task_id=task_id, _task_update=_task_update
    )
    if not page_items:
        return None

    # Filter out already processed dailyFX assets for automatic runs (case-insensitive)
    if not selected_asset_ids:
        original_count = len(page_items)
        page_items = [
            item for item in page_items
            if not (
                getattr(item, "original_file_name", None)
                and "dailyfx" in getattr(item, "original_file_name", "").lower()
            )
        ]
        removed_count = original_count - len(page_items)
        if removed_count > 0:
            debug_log(
                "Filtered out processed dailyFX assets from selection",
                task_id=task_id,
                removed_count=removed_count,
            )

    unique_items = _dedupe_page_items(page_items)
```

**Step 2: Run tests to verify they pass**

Run: `pytest backend/tests/test_engine.py -k test_prepare_page_items_ -v`
Expected: PASS.

Run all tests: `make backend-test`
Expected: PASS.

**Step 3: Commit**

```bash
git add backend/app/services/generation/pipeline/assets.py
git commit -m "feat: exclude dailyFX-processed assets from automatic selection based on filename"
```

---

### Task 3: Bump Version of Application

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/version.ts`
- Modify: `frontend/package-lock.json`

**Step 1: Bump the version string from `0.3.15` to `0.3.16`**

- In `frontend/package.json`: change `"version": "0.3.15"` to `"version": "0.3.16"`
- In `frontend/src/version.ts`: change `export const APP_VERSION = '0.3.15';` to `export const APP_VERSION = '0.3.16';`
- In `frontend/package-lock.json`: change version fields to `"0.3.16"`

**Step 2: Build the frontend**

Run: `cd frontend && npm run build`
Expected: Success.

**Step 3: Run frontend tests**

Run: `cd frontend && npm test`
Expected: PASS.

**Step 4: Commit**

```bash
git add frontend/package.json frontend/src/version.ts frontend/package-lock.json
git commit -m "frontend: bump version to 0.3.16"
```
