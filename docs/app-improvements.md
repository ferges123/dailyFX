# App Improvements

Notes from a second pass over the application, excluding security topics.

## Highest Priority

1. Split the generation pipeline into explicit stages.
   `backend/app/services/generation/engine.py` currently handles module selection, asset lookup, AI Vision, image generation, EXIF embedding, history writes, task state, and notifications in one function. Extracting separate stages for planning, metadata, persistence, and notifications would make the flow easier to test and much easier to change without regressions.

2. Unify the schedule-triggered run paths.
   The selected-schedule manual trigger and the scheduler both rebuild very similar filter and payload logic in slightly different ways. A shared task payload builder and shared validation layer would reduce drift between `backend/app/api/routes_schedules.py` and `backend/app/workers/scheduler.py`.

3. Make AI metadata provenance explicit.
   Title, summary, and tags now come from multiple possible sources: source Vision, final Vision, module defaults, or fallback values. That works, but it is hard to reason about from the history UI alone. A single metadata source field or a structured trace in `config_json` would make debugging and support easier.
   Status: implemented via `metadata_provenance` in `config_json`, plus history/review UI rendering.

4. Improve task observability.
   The app already tracks `step`, `progress`, history, and SSE events, but the detailed generation timeline is still fragmented across logs and history entries. A compact per-task timeline in the history UI would help explain where a run spent time and why it ended up with particular metadata.
   Status: implemented via `task_trace` in `config_json` and a visible timeline in History/review.

## Medium Priority

5. Break up `HistoryPage`.
   `frontend/src/pages/History/HistoryPage.tsx` currently owns infinite query state, SSE streaming, selection, EXIF loading, upload/retry/reject mutations, and rendering. Extracting hooks such as `useHistoryStream`, `useSelectedHistoryEntry`, and `useHistoryMutations` would make the page easier to maintain.
   Status: implemented via dedicated history filters, query, selection, and stream hooks.

6. Tighten the upload/retry duplication.
   The accept and retry handlers in `backend/app/api/routes_generation.py` share most of their logic. A single upload helper would keep metadata, album handling, and tag application consistent across both paths.
   Status: implemented via shared upload, caption, and tag helpers in `backend/app/api/routes_generation.py`.

7. Normalize AI effect configuration.
   The AI modules share a lot of prompt, image preparation, and fallback behavior, but the shape is still spread across `ai_style_base.py` and per-effect modules. A stronger base abstraction for `ai_*` effects would reduce duplication and make new AI styles cheaper to add.
   Status: implemented by moving all `ai_*` modules onto a shared `AIStyleBaseModule` plus a shared image-byte helper.

## UX

8. Add a stronger source-vs-result comparison in History.
   The current review flow shows the source link, but AI results would be easier to judge with a more explicit comparison view between the original photo and the generated result.

9. Add API contract tests for the key response shapes.
   Tests that validate exact JSON for core endpoints such as Immich options/assets and generation history make response-model regressions much harder to miss.
   Status: implemented via dedicated contract tests in `backend/tests/test_api_contracts.py`.

10. Expand the documentation of the AI metadata pipeline.
   The current docs now include a dedicated AI metadata pipeline section in `docs/api.md`, covering `people_context`, source Vision, final Vision, `metadata_provenance`, and `task_trace`.
   Status: implemented.

## Suggested Order

1. Refactor the generation pipeline.
2. Make AI metadata provenance explicit.
3. Unify the schedule trigger/scheduler task flow.
4. Split the history page into smaller hooks.
