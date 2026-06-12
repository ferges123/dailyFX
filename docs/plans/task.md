# Task Tracker - DailyFX Application Stabilization

| Task | Status | Details |
|------|--------|---------|
| Task 1: version single source of truth | Completed | Made version metadata consistent across backend/frontend and updated tests. |
| Task 2: lazy routes and error boundaries | Completed | Added React.lazy imports and RouteErrorBoundary in App.tsx. |
| Task 3: shallow Docker healthcheck cleanup | Completed | Moved healthcheck from inline python to healthcheck.py and updated compose config. |
| Task 4: split `Presets.tsx` | Completed | Split Presets.tsx into multiple files by tab component boundaries. |
| Task 5: split `Schedules.tsx` | Not Started | Split Schedules.tsx after setting up unit tests. |
| Task 6: split `Settings.tsx` | Completed | Split Settings.tsx into sections. |
| Task 7: API-boundary effect config validation | Completed | Created validation service and enforced it at preset and studio routes. |
| Task 8: split `ai_vision.py` | Completed | Split into provider-specific adapter package and refactored tests. |
| Task 9: extract pipeline stages | Not Started | Split pipeline execution into separate files. |
| Task 10: split notification providers | Completed | Split into provider-specific adapter modules under notifications/providers/ |
| Task 11: rate limits | Not Started | Apply per-endpoint rate limits. |
| Task 12: Content Security Policy | Not Started | Add CSP to frontend Nginx. |
| Task 13: comparator in history | Not Started | Add before/after image comparator. |
| Task 14: bulk actions | Not Started | Add bulk accept/reject endpoints and UI. |
| Task 15: metrics and structured logging | Not Started | Add Prometheus-like metrics and JSON logging. |
