# Design: Exclude dailyFX Processed Photos from AI/Random Selection

## 1. Overview
When dailyFX generates and uploads an effect-applied photo to Immich, it appends `_dailyFX` to the filename (e.g. `image_dailyFX.jpg`). During automatic or AI-based random cycles, we must immediately reject these already-processed photos from the candidate list so they are not analyzed by AI or selected for further processing. This avoids wasting AI Vision API tokens and prevents processing already-processed photos.

The user has selected **Option A**: if some assets are rejected, we proceed with the remaining clean assets (e.g., 3 candidates instead of 4), rather than looping back to request more random assets.

---

## 2. Design Details
The filtering will be performed in the backend generation pipeline asset preparation function:
* **File:** [assets.py](file:///opt/dailyFX/backend/app/services/generation/pipeline/assets.py)
* **Function:** `_prepare_page_items_for_module`

### Rules
1. **Case-insensitive matching:** Any asset whose `original_file_name` contains `"dailyfx"` (case-insensitive) will be rejected.
2. **Scoping:** The filter applies to all automatic/random runs (i.e. when `selected_asset_ids` is empty/None).
3. **Manual Selection Override:** If a user explicitly selects photo IDs via `selected_asset_ids`, they are not filtered out, allowing manual overrides/reprocessing.

---

## 3. Proposed Code Changes

### File: `backend/app/services/generation/pipeline/assets.py`
We will insert the filter block inside `_prepare_page_items_for_module` before deduplication:

```python
def _prepare_page_items_for_module(
    *,
    page,
    module,
    selected_asset_ids: list[str] | None,
    ai_photo_selection_enabled: bool,
    task_id: str,
    _task_update: Callable[..., None],
) -> list | None:
    page_items = _select_page_items(
        page=page, selected_asset_ids=selected_asset_ids, task_id=task_id, _task_update=_task_update
    )
    if not page_items:
        return None

    # Filter out already processed dailyFX assets for automatic runs
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
    if not unique_items:
        return None

    source_asset_count = max(1, int(getattr(module, "source_asset_count", 1) or 1))
    if source_asset_count > 1:
        return unique_items[:source_asset_count]
    if ai_photo_selection_enabled:
        return unique_items[:4]
    return page_items
```

---

## 4. Test Plan
We will write unit tests inside `backend/tests/test_engine.py` to cover:
1. **Successful filtering:** A list of candidates containing both fresh and dailyFX-processed assets should be filtered down to only fresh assets when `selected_asset_ids` is None.
2. **Case-insensitive matching:** Filenames like `photo_dailyFX.jpg`, `photo_DAILYFX.PNG`, and `photo_dailyfx.jpeg` are all successfully filtered out.
3. **Manual Selection Override:** When `selected_asset_ids` is provided, files containing `dailyfx` in their name are NOT filtered out.
