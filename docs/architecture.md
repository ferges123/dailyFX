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
  - `pipeline.py` orchestrates the generation run using an explicit, decoupled staged pipeline (Planning, Asset Retrieval, Module Execution, Metadata Enrichment, Persistence, and Notification Dispatch).
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

The generation pipeline is decoupled into six explicit, testable stages defined in [pipeline.py](file:///home/ferges/Projects/dailyFX/backend/app/services/generation/pipeline.py), sharing state via the `GenerationPipelineContext` structure:

1. **Setup & Planning (`_pipeline_setup_and_planning`):** Resolves schedule settings, sets up debug logging, updates task status to running, and selects the generation module to run based on preset weights.
2. **Asset Retrieval & Selection (`_pipeline_retrieve_and_select_assets`):** Connects to Immich to search for candidate assets matching the filter presets and performs AI-driven selection/ranking if enabled.
3. **Module Execution (`_pipeline_execute_module`):** Runs the selected creative module (OpenCV/Pillow filters) or calls generative AI models (BytePlus/etc.).
4. **Metadata & Vision Enrichment (`_pipeline_enrich_metadata`):** Resolves people and source contexts, runs prompt enrichment, and generates final vision metadata (titles, summaries, tags).
5. **Post-Processing & Persistence (`_pipeline_persist_result`):** Encapsulates task completion tracking, writes the generated image to disk, embeds EXIF metadata, and saves the history entry.
6. **Notification Dispatch (`_pipeline_dispatch_notifications`):** Sends Telegram alerts and triggers configured webhooks.

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
