# Architecture

DailyFX is split into a small set of layers so the API contract, generation flow, and UI can evolve independently.

## High-Level Flow

1. The frontend or background scheduler loop selects a schedule and builds a generation task.
2. The API validates the request, stores task state, and hands off work to the worker flow.
3. The generation pipeline selects a module, fetches assets from Immich, and runs the effect.
4. Optional AI Vision runs on the source asset and, for `ai_*` modules, again on the final image.
5. The pipeline embeds EXIF, writes the generated file, stores history, and records provenance.
6. The review UI reads the history entry, status, and trace data, then accepts or rejects the result.

## Backend Layers

- `app/api/`
  - Thin FastAPI routes.
  - Handles validation, response models, and request/response shape.
  - Should not contain core generation or persistence logic.
- `app/services/generation/`
  - `pipeline.py` orchestrates the generation run.
  - `engine.py` preserves compatibility for tests and shared entry points.
  - `persistence.py` writes the generated file and history entry.
  - `output.py` dispatches notifications and webhook calls.
  - `history.py` manages history queries, updates, and trace entries.
  - `modules/` contains generation effect implementations.
- `app/services/settings/`
  - Holds helpers for response shaping and connection tests.
- `app/services/notifications/`
  - Holds preset-specific notification test helpers.
- `app/workers/`
  - Runs the background scheduler loop and queued manual tasks.

## Contract Boundary

The domain models live in `app.immich.models` and the generation/service models under `app.models`.
Response models in `app.schemas` are thin adapters around those domain objects.

That means:

- domain models define the business data,
- schemas define the API contract,
- routes translate between the two.

This keeps JSON shape changes explicit and testable.

## Generation Flow

The generation pipeline is intentionally staged:

- select a generation module from the enabled preset groups,
- search Immich for matching assets,
- pick the final asset set,
- run the selected module,
- resolve source asset context and people context,
- run source Vision when enabled,
- run final Vision for `ai_*` modules,
- inject tags and capture provenance,
- embed EXIF metadata,
- persist the file and history entry,
- dispatch notifications and webhooks.

The visible timeline for a task comes from history trace entries, not from logs alone.

## History And Review

The history record is the canonical source for:

- task status,
- title and summary,
- provider and model,
- output path,
- review/accept/reject state,
- `metadata_provenance`,
- `task_trace`.

The history page and review UI should treat that record as the source of truth.

## Testing Strategy

The repository uses two main kinds of backend tests:

- contract tests that pin exact JSON for stable endpoints,
- flow tests that verify orchestration, state transitions, and error handling.

The contract tests live under `backend/tests/contracts/` and are documented there.
