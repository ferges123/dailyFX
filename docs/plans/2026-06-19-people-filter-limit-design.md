# Design Document: Increase People Filter Limit from 20 to 33

## Problem
In the Filter Presets page, when selecting people for filters, the dropdown/list of available people is limited to 20. The user requested to change this limit to 33.

## Proposed Solution (Approach 1)
Modify the hardcoded slice limit of `20` in the backend's Immich client when fetching and sorting people by asset count.

## Detailed Changes

### 1. Backend Changes
In `/opt/dailyFX/backend/app/immich/client.py`:
- Locate the `list_people` method.
- Update `return enriched[:20]` to `return enriched[:33]`.

### 2. Test Updates
In `/opt/dailyFX/backend/tests/test_immich_client.py`:
- Ensure that mock tests for `list_people` are compatible and continue to pass.

### 3. Version Bump
Following the repository guidelines, update the version from `0.3.19` to `0.3.20` in the following files:
- `/opt/dailyFX/frontend/package.json`
- `/opt/dailyFX/frontend/src/App.tsx`
- `/opt/dailyFX/frontend/src/pages/Settings.tsx`
