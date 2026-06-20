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
  - Centralized exception mapping is managed in `app/main.py` using custom exception handlers (converting model validation and domain-specific errors such as `ValueError`, `LocalAIConfigurationError`, and `StudioUploadValidationError` to clean API error payloads).
  - Should not contain core generation or persistence logic.
- `app/services/generation/`
  - `pipeline/` package orchestrates the generation run using an explicit, decoupled staged pipeline split into modular files: `planning.py`, `assets.py`, `execution.py`, `metadata.py`, `persistence.py`, and `notifications.py` (with context/helpers in `shared.py` and coordination in `__init__.py`).
  - `vision/` package houses provider-specific AI vision adapters (`gemini.py`, `openai.py`, `openrouter.py`, `xiaomi.py`, `local.py`) derived from a common `base.py` interface.
  - `config_validation.py` enforces parameter constraint validation at preset save and studio preview API boundaries.
  - `engine.py` preserves compatibility for tests and shared entry points.
  - `persistence.py` writes the generated file and history entry.
  - `output.py` dispatches notifications and webhook calls.
  - `history.py` manages history queries, updates, and trace entries.
  - `modules/` contains generation effect implementations.
- `app/services/studio/`
  - Validation, local asset handling, and helpers for the Studio page preview flow.
- `app/services/settings/`
  - Holds helpers for settings management and connection tests.
- `app/services/local_ai.py`
  - Local AI provider support (e.g. self-hosted OpenAI-compatible endpoints).
- `app/services/notifications/`
  - Holds preset-specific notification test helpers, delegating to the unified notification client.
- `app/notifications/`
  - `client.py` orchestrates notification delivery.
  - `providers/` package contains modular integrations (`telegram.py`, `home_assistant.py`, `slack.py`, `discord.py`, `gotify.py`, `ntfy.py`, `apprise.py`, `web.py`) inheriting from `base.py`.
- `app/workers/`
  - `scheduler.py` — runs the background scheduler loop and queued manual tasks.
  - `telegram_bot.py` — Telegram bot worker for interactive notification buttons.
- `app/observability/`
  - Structured logging setup (`logging.py`).

## Contract Boundary

The domain models live in `app.immich.models` and the generation/service models under `app.models`.
Response models in `app.schemas` are thin adapters around those domain objects.

That means:

- domain models define the business data,
- schemas define the API contract,
- routes translate between the two.

This keeps JSON shape changes explicit and testable.

## Generation Flow

The generation pipeline is decoupled into six explicit, testable stages defined in the [pipeline/](file:///opt/dailyFX/backend/app/services/generation/pipeline/) package, sharing state via the `GenerationPipelineContext` structure:

1. **Setup & Planning (`_pipeline_setup_and_planning`):** Resolves schedule settings, sets up debug logging, updates task status to running, and selects the generation module to run based on preset weights.
2. **Asset Retrieval & Selection (`_pipeline_retrieve_and_select_assets`):** Connects to Immich to search for candidate assets matching the filter presets (requesting a random pool of 30 assets to prevent duplicates). It applies history-based deduplication by checking the last 25 unique source asset IDs from the generation history, sorting them to prefer unused or oldest-used images (bypassed if explicit assets are selected manually), and performs AI-driven selection/ranking if enabled.
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
