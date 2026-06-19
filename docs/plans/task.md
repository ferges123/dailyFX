# Live Tracker: Increase People Filter Limit

| Task | Status | Details |
| :--- | :--- | :--- |
| Task 1: Add failing unit test for 33 people limit | Pending | Add `test_list_people_limits_to_33` in `backend/tests/test_immich_client.py` and verify failure |
| Task 2: Update backend Immich client list limit | Pending | Change limit slice from `[:20]` to `[:33]` and verify unit tests pass |
| Task 3: Bump application version to 0.3.20 | Pending | Update `package.json`, `package-lock.json`, and `version.ts` to `0.3.20` and verify builds and tests pass |
