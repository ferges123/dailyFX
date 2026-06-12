# DailyFX Application Stabilization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce maintenance risk in DailyFX by fixing version drift, improving route resilience, splitting the highest-risk large files, and moving security/validation work ahead of non-essential feature expansion.

**Architecture:** Keep current FastAPI, SQLAlchemy, Vite, React, Tailwind, and TanStack Query architecture. Prefer extraction into focused modules over behavior changes, and keep compatibility with existing API shapes unless a task explicitly introduces a contract change. Refactors must preserve current UI routes and backend endpoints.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Alembic, SQLite WAL, React 19, Vite 8, TypeScript 6, Tailwind 4, TanStack Query, Vitest, pytest, Docker Compose.

---

## Plan Execution Status

| Task | Description | Completed By | Status |
|------|-------------|--------------|--------|
| **Task 1** | Make Application Version A Single Source Of Truth | Previous Agent | Completed |
| **Task 2** | Add Lazy Route Loading And Route Error Boundaries | Previous Agent | Completed |
| **Task 3** | Keep Docker Healthcheck Shallow But Move Logic Out Of Inline Python | Antigravity | Completed |
| **Task 4** | Split `Presets.tsx` By Existing Tabs | Antigravity | Completed |
| **Task 6** | Split `Settings.tsx` Into Sections | Antigravity | Completed |
| **Task 7** | Validate Effect Configs At API Boundaries | Antigravity | Completed |

---

## Current Findings

This file replaces the original read-only audit from 2026-06-12 with an execution-oriented plan.

### Confirmed High-Risk Files

| File | Lines | Assessment |
|------|-------|------------|
| `frontend/src/pages/Presets.tsx` | 2128 | Highest-value frontend split. It already contains clear boundaries: filter presets, effect presets, and notification presets. |
| `frontend/src/pages/Schedules.tsx` | 1320 | Worth splitting, but not a quick win. It combines routing, list rendering, form state, mutations, validation, and provider model selection. |
| `backend/app/services/generation/pipeline.py` | 1447 | Already has stage-like functions and a central orchestrator, but the file is too large for safe iteration. Extract only after tests are stable. |
| `backend/app/services/generation/ai_vision.py` | 1046 | Good provider-adapter split candidate. OpenAI, Gemini, OpenRouter, Xiaomi, and local provider paths are independent enough to separate. |
| `frontend/src/pages/Settings.tsx` | 839 | Borderline. Split after lower-risk frontend structure is established. |
| `frontend/src/api/client.ts` | 770 | Borderline. Do not rewrite before route/page refactors settle. |
| `frontend/src/pages/AIEffects.tsx` | 721 | Borderline. Split only when touching AI effect editing or import/export behavior. |
| `backend/app/notifications/client.py` | 510 | Moderate backend split candidate. Per-provider notification clients can follow the AI Vision provider pattern. |

### Corrections To The Earlier Audit

- `slowapi` rate limiting already exists globally in `backend/app/main.py`; the missing work is per-endpoint tuning, not adding rate limiting from scratch.
- Effect config validation already exists in `backend/app/services/generation/pipeline.py`; the missing work is API-boundary validation and rejection of unknown config keys before pipeline execution.
- Contract tests already exist under `backend/tests/contracts/`; the missing work is an endpoint coverage inventory and tests for uncovered routes.
- `/api/health/detailed` exists and requires auth. It should not simply replace the Docker healthcheck because it can perform deeper checks and may create false container restarts.
- `pipeline.py` already has named stages. The goal is extraction to focused files, not inventing a new pipeline model.

## Execution Rules

- Keep each task behavior-preserving unless the task explicitly says it changes behavior.
- Write or update tests before refactoring files with user-visible behavior.
- Run the narrow test suite for each task before broad verification.
- Do not mix UI feature work with backend refactors in the same task.
- Do not build a new Docker image until the version is bumped according to repository rules.

## Phase 1: Low-Risk Stabilization

### Task 1: Make Application Version A Single Source Of Truth

**Why:** The frontend shows `0.2.14`, while backend metadata and `/api/health` still return `0.1.0`. This creates confusing diagnostics and breaks release hygiene.

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/Settings.tsx`
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/routes_health.py`
- Test: `frontend/src/__tests__/App.test.tsx`
- Test: `frontend/src/__tests__/Settings.test.tsx`
- Test: backend health tests if present; otherwise add focused coverage in `backend/tests/test_settings_routes.py` or a new `backend/tests/test_health.py`

- [x] Add a backend-accessible version constant, preferably in `backend/app/config.py` or a small `backend/app/version.py`, with the same SemVer string used by the frontend.
- [x] Update `FastAPI(..., version=...)` and `/api/health` to use that constant instead of hard-coded `0.1.0`.
- [x] Update frontend display strings only through one imported constant or package-derived value.
- [x] Update tests that currently assert `0.1.0`.
- [x] Run `cd frontend && npm test -- App.test.tsx Settings.test.tsx`.
- [x] Run `make backend-test` or the narrow health/settings pytest target.

### Task 2: Add Lazy Route Loading And Route Error Boundaries

**Why:** `frontend/src/App.tsx` imports all major pages immediately. Lazy loading lowers initial bundle weight, and per-route boundaries prevent one page crash from taking down the whole app shell.

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/RouteErrorBoundary.tsx`
- Test: `frontend/src/__tests__/App.test.tsx`

- [x] Create a route error boundary component using React class boundary semantics.
- [x] Convert page imports for History, Studio, Schedules, Presets, AI Effects, Settings, and Login to `React.lazy`.
- [x] Wrap route elements with `Suspense` and route-level error boundary.
- [x] Preserve the current `/` to `/history` redirect and nested `/presets/*` routes.
- [x] Add a test that verifies the app still renders the default authenticated route.
- [x] Run `cd frontend && npm test -- App.test.tsx`.
- [ ] Run `cd frontend && npm run build`.

### Task 3: Keep Docker Healthcheck Shallow But Move Logic Out Of Inline Python

**Why:** The current `docker-compose.yml` healthcheck uses an inline Python expression. Replacing it with `/api/health/detailed` is risky because detailed health requires auth and checks external dependencies. The better fix is a small unauthenticated shallow health script or endpoint.

**Files:**
- Modify: `docker-compose.yml`
- Create or modify: `backend/app/api/routes_health.py`
- Optional create: `backend/healthcheck.py`
- Test: backend health tests

- [x] Keep the healthcheck shallow: API process responds and scheduler heartbeat is fresh.
- [x] Do not call `/api/health/detailed` from Docker healthcheck.
- [x] If adding `backend/healthcheck.py`, make it call `/api/health` and check `/data/scheduler.health` with clear exit codes.
- [x] Update `docker-compose.yml` to call the script instead of inline Python.
- [x] Run the focused backend health test.
- [x] Run `docker compose config` to validate compose syntax.

## Phase 2: Frontend Refactors With Existing Behavior Preserved

### Task 4: Split `Presets.tsx` By Existing Tabs

**Why:** This is the safest high-value frontend split because the file already has natural page boundaries and exported wrappers.

**Files:**
- Modify: `frontend/src/pages/Presets.tsx`
- Create: `frontend/src/pages/Presets/PresetHeader.tsx`
- Create: `frontend/src/pages/Presets/FilterPresetsPage.tsx`
- Create: `frontend/src/pages/Presets/EffectPresetsPage.tsx`
- Create: `frontend/src/pages/Presets/NotificationPresetsPage.tsx`
- Create: `frontend/src/pages/Presets/presetComponents.tsx`
- Create: `frontend/src/pages/Presets/presetUtils.ts`
- Test: `frontend/src/__tests__/Presets.test.tsx`

- [x] Move shared presentational helpers first: `PresetHeader`, `PresetFormActions`, `PresetActionRow`.
- [x] Move filter preset components and state into `FilterPresetsPage.tsx`.
- [x] Move effect preset components and state into `EffectPresetsPage.tsx`.
- [x] Move notification preset components and state into `NotificationPresetsPage.tsx`.
- [x] Keep `frontend/src/pages/Presets.tsx` as a compatibility export barrel if imports currently depend on it.
- [x] Run `cd frontend && npm test -- Presets.test.tsx`.
- [x] Run `cd frontend && npm run build`.

### Task 5: Split `Schedules.tsx` Only After Locking Tests

**Why:** This file is riskier than `Presets.tsx` because route state, form state, mutation state, and provider model selection are intertwined.

**Files:**
- Modify: `frontend/src/pages/Schedules.tsx`
- Create: `frontend/src/pages/Schedules/ScheduleSummaryCard.tsx`
- Create: `frontend/src/pages/Schedules/ScheduleList.tsx`
- Create: `frontend/src/pages/Schedules/ScheduleForm.tsx`
- Create: `frontend/src/pages/Schedules/scheduleFormState.ts`
- Create: `frontend/src/pages/Schedules/scheduleUtils.ts`
- Test: `frontend/src/__tests__/Schedules.test.tsx`

- [ ] Add or confirm tests for creating, editing, toggling, deleting, and running a schedule.
- [ ] Move pure helpers first: status badge logic, count helpers, form conversion, model normalization.
- [ ] Extract summary cards and list rendering.
- [ ] Extract the form only after helper and list extraction tests pass.
- [ ] Preserve `/schedules`, `/schedules/new`, and `/schedules/:scheduleId/edit`.
- [ ] Run `cd frontend && npm test -- Schedules.test.tsx`.
- [ ] Run `cd frontend && npm run build`.

### Task 6: Split `Settings.tsx` Into Sections

**Why:** Settings is borderline large and provider-heavy. Split only after version handling is centralized so the footer and health display do not keep drifting.

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`
- Create: `frontend/src/pages/Settings/RuntimeStatusSection.tsx`
- Create: `frontend/src/pages/Settings/ConnectionTestsSection.tsx`
- Create: `frontend/src/pages/Settings/AIProviderSettingsSection.tsx`
- Create: `frontend/src/pages/Settings/settingsValidation.ts`
- Test: `frontend/src/__tests__/Settings.test.tsx`

- [x] Move validation helpers into `settingsValidation.ts`.
- [x] Move runtime health rendering into `RuntimeStatusSection.tsx`.
- [x] Move connection test controls into `ConnectionTestsSection.tsx`.
- [x] Move AI provider/model controls into `AIProviderSettingsSection.tsx`.
- [x] Preserve current save and connection-test behavior.
- [x] Run `cd frontend && npm test -- Settings.test.tsx`.
- [x] Run `cd frontend && npm run build`.

## Phase 3: Backend Validation And Provider Refactors

### Task 7: Validate Effect Configs At API Boundaries

**Why:** Pipeline validation is late. API routes should reject invalid or unknown config keys before a generation task starts or a preset is saved.

**Files:**
- Modify: `backend/app/services/generation/pipeline.py`
- Create: `backend/app/services/generation/config_validation.py`
- Modify: `backend/app/api/routes_generation.py`
- Modify: `backend/app/api/routes_presets.py`
- Modify: `backend/app/api/routes_schedules.py`
- Modify: `backend/app/api/routes_studio.py`
- Test: `backend/tests/test_generation_routes.py`
- Test: `backend/tests/test_presets_routes.py`
- Test: `backend/tests/test_schedule_contracts.py`
- Test: `backend/tests/test_studio_routes.py`

- [x] Move current `_validate_module_config` logic into `config_validation.py`.
- [x] Extend validation to reject unknown keys except explicitly allowed metadata keys already used by the app.
- [x] Call validation before saving effect presets and before starting manual/studio/scheduled generation.
- [x] Keep error responses stable and human-readable.
- [x] Run the focused backend tests for generation, presets, schedules, and studio.

### Task 8: Split `ai_vision.py` Into Provider Adapters

**Why:** Provider-specific request/response handling is independent and should not live in one 1000+ line file.

**Files:**
- Modify: `backend/app/services/generation/ai_vision.py`
- Create: `backend/app/services/generation/vision/__init__.py`
- Create: `backend/app/services/generation/vision/base.py`
- Create: `backend/app/services/generation/vision/openai.py`
- Create: `backend/app/services/generation/vision/gemini.py`
- Create: `backend/app/services/generation/vision/openrouter.py`
- Create: `backend/app/services/generation/vision/xiaomi.py`
- Create: `backend/app/services/generation/vision/local.py`
- Test: `backend/tests/test_ai_vision.py`

- [ ] Move shared types and helpers into `vision/base.py`.
- [ ] Move one provider at a time, starting with OpenAI.
- [ ] Keep public imports `analyze_image`, `analyze_images`, `AIVisionResult`, and `AIVisionError` compatible.
- [ ] After each provider move, run `python3 -m pytest backend/tests/test_ai_vision.py` from the repository root or the existing backend test command.
- [ ] Do not change default model choices in this refactor.

### Task 9: Extract Pipeline Stages After Validation Tests Pass

**Why:** `pipeline.py` already has stages. Extracting before validation and provider tests are stable would add risk without increasing confidence.

**Files:**
- Modify: `backend/app/services/generation/pipeline.py`
- Create: `backend/app/services/generation/pipeline_context.py`
- Create: `backend/app/services/generation/stages/planning.py`
- Create: `backend/app/services/generation/stages/assets.py`
- Create: `backend/app/services/generation/stages/module_execution.py`
- Create: `backend/app/services/generation/stages/metadata.py`
- Create: `backend/app/services/generation/stages/persistence.py`
- Create: `backend/app/services/generation/stages/notifications.py`
- Test: `backend/tests/test_pipeline_stages.py`
- Test: `backend/tests/test_generation_routes.py`

- [ ] Move `GenerationPipelineContext`, `GenerationModuleSelection`, and `GenerationArtifacts` to `pipeline_context.py`.
- [ ] Move one stage function per commit-sized step.
- [ ] Keep `run_generation_pipeline` in `pipeline.py` as the orchestrator.
- [ ] Run `backend/tests/test_pipeline_stages.py` after every stage extraction.
- [ ] Run generation route tests after the final extraction.

### Task 10: Split Notification Providers

**Why:** `backend/app/notifications/client.py` has multiple independent providers. Split after AI Vision provider extraction establishes the adapter pattern.

**Files:**
- Modify: `backend/app/notifications/client.py`
- Create: `backend/app/notifications/providers/base.py`
- Create: `backend/app/notifications/providers/ntfy.py`
- Create: `backend/app/notifications/providers/gotify.py`
- Create: `backend/app/notifications/providers/telegram.py`
- Create: `backend/app/notifications/providers/home_assistant.py`
- Create: `backend/app/notifications/providers/apprise.py`
- Create: `backend/app/notifications/providers/discord.py`
- Create: `backend/app/notifications/providers/slack.py`
- Test: `backend/tests/test_notifications.py`
- Test: `backend/tests/test_notification_preset_tests.py`

- [ ] Extract shared request/error helpers first.
- [ ] Move one notification provider at a time.
- [ ] Preserve existing function names exported by `client.py` until all call sites are migrated.
- [ ] Run notification tests after each provider move.

## Phase 4: Security, UX, And Monitoring

### Task 11: Add Per-Endpoint Rate Limits

**Why:** Global `120/minute` is coarse. Auth, generation start, accept/reject, and read-only endpoints need different limits.

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/routes_generation.py`
- Modify: `backend/app/api/routes_settings.py`
- Modify: `backend/app/api/routes_studio.py`
- Modify: `backend/app/api/routes_presets.py`
- Modify: `backend/app/security.py`
- Test: `backend/tests/test_security.py`

- [ ] Keep the existing global limiter.
- [ ] Add stricter limits to login/auth-like flows and generation start routes.
- [ ] Keep read-only history and module endpoints less restrictive than mutation endpoints.
- [ ] Add tests that prove a strict endpoint returns `429` after the configured threshold.

### Task 12: Add Content Security Policy

**Why:** The app serves a browser UI and review page. CSP should be explicit before the app is exposed outside a trusted LAN.

**Files:**
- Modify: `frontend/nginx.conf`
- Modify: `frontend/Dockerfile` only if the nginx config copy path is not already wired
- Test: frontend build and a header check against a running container

- [ ] Add CSP that allows the current app, API calls, images, service worker, and push features without allowing broad unsafe origins.
- [ ] Verify the app still loads, images render, and service worker registration is not broken.

### Task 13: Add Before/After Comparator In History

**Why:** This overlaps with `docs/plans/app-improvements.md` and is a user-visible improvement with clear value, but it should follow route/error-boundary stabilization.

**Files:**
- Modify: `frontend/src/pages/History/LightboxModal.tsx`
- Modify: `frontend/src/pages/History/HistoryDetailPanel.tsx`
- Test: `frontend/src/__tests__/History.test.tsx`

- [ ] Add a comparison view only for entries with both source and generated images.
- [ ] Keep the existing modal behavior for entries without source images.
- [ ] Use existing `SecureImage` behavior for authenticated image loading.
- [ ] Run `cd frontend && npm test -- History.test.tsx`.

### Task 14: Add Bulk Accept/Reject

**Why:** Useful, but it changes API and UI behavior. Do this after accept/reject error handling and history tests are strong.

**Files:**
- Modify: `backend/app/api/routes_generation.py`
- Modify: `backend/app/schemas/generation.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/History/HistoryPage.tsx`
- Test: `backend/tests/test_generation_routes.py`
- Test: `frontend/src/__tests__/History.test.tsx`

- [ ] Add backend request/response schemas for bulk actions.
- [ ] Reuse existing single-item accept/reject logic internally.
- [ ] Return per-task success/error results instead of failing the whole batch on one bad item.
- [ ] Add UI multi-select action controls.
- [ ] Run focused backend and frontend history tests.

### Task 15: Add Metrics And Structured Logging

**Why:** Useful for production observability, but lower priority than validation, versioning, and maintainability.

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/app/api/routes_metrics.py`
- Create: `backend/app/observability/logging.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_health.py`
- Test: `backend/tests/test_security.py`

- [ ] Decide whether `/metrics` is unauthenticated, token-protected, or disabled by default via config.
- [ ] Add JSON logging behind a config flag if current plain logs are still useful for local development.
- [ ] Track queue/task counts without expensive queries on every scrape.
- [ ] Add route tests for metrics availability and protection mode.

## Deferred Work

These items are valid but should not block stabilization:

- Dark mode.
- Infinite scroll in History.
- Keyboard shortcuts.
- Multi-stage Docker image size reduction.
- CI expansion for Alembic, lint, format, and E2E.
- Webhook retry queue.
- Full custom AI style creator and sandbox features from `docs/plans/app-improvements.md`.

## Recommended Order

1. Task 1: version single source of truth.
2. Task 2: lazy routes and error boundaries.
3. Task 3: shallow Docker healthcheck cleanup.
4. Task 4: split `Presets.tsx`.
5. Task 7: API-boundary effect config validation.
6. Task 8: split `ai_vision.py`.
7. Task 5: split `Schedules.tsx`.
8. Task 9: extract pipeline stages.
9. Task 11 and Task 12: rate limits and CSP.
10. Task 13 and Task 14: comparator and bulk actions.

## Verification Baseline

Run these before declaring the stabilization sequence complete:

```bash
cd frontend && npm test
cd frontend && npm run build
make backend-test
docker compose config
```
