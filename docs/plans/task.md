# Plan: Exclude dailyFX Processed Photos

| Task | Status | Details |
| :--- | :---: | :--- |
| Task 1: Write and Verify Failing Unit Tests | ✅ completed | Add unit tests to `backend/tests/test_engine.py` for filename exclusion and manual override. |
| Task 2: Implement Asset Exclusion Logic in assets.py | ✅ completed | Filter assets in `_prepare_page_items_for_module` when no `selected_asset_ids` are provided. |
| Task 3: Bump Version of Application | ✅ completed | Bump version from 0.3.15 to 0.3.16 in `package.json`, `version.ts`, and `package-lock.json`. |
