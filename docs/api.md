# DailyFX for immich API

This document describes the public backend API used by the DailyFX frontend and external integrations.

## Base URL

All endpoints are served under:

```text
/api
```

For a local instance:

```text
http://localhost:8438/api
```

## Authentication

If `APP_ACCESS_TOKEN` is set, most endpoints require:

```http
Authorization: Bearer <token>
```

Some read-only review endpoints remain public and are noted below.

## Response notes

- Rate limit: `120/minute` per client IP by default.
- Strict rate limits apply to sensitive endpoints:
  - `POST /api/settings/test-immich` and `POST /api/settings/test-provider/{provider}`: `10/minute`
  - `PUT /api/settings`: `10/minute`
  - `POST /api/schedules/{schedule_id}/run-now`: `10/minute`
  - `POST /api/studio/preview`: `5/minute`
- Errors are returned as JSON with a `detail` field
- Some endpoints return binary content such as PNG, JPEG, HTML, or plain text

## Endpoint Map

| Area | Endpoints |
|---|---|
| Health | `GET /api/health`, `GET /api/health/detailed` |
| Settings | `GET /api/settings`, `PUT /api/settings`, `POST /api/settings/test-immich`, `POST /api/settings/test-provider/{provider}`, `GET /api/settings/models/{provider}` |
| Immich | `GET /api/immich/options`, `GET /api/immich/assets`, `GET /api/immich/assets/{asset_id}/thumbnail`, `GET /api/immich/assets/{asset_id}/exif` |
| Presets | CRUD for `filters`, `effects`, `notifications` |
| Schedules | CRUD plus `POST /api/schedules/{schedule_id}/run-now` |
| AI Effects | `GET /api/ai-effects`, `POST /api/ai-effects`, `PUT /api/ai-effects/{effect_id}`, `DELETE /api/ai-effects/{effect_id}`, `POST /api/ai-effects/{effect_id}/reset`, `POST /api/ai-effects/{effect_id}/duplicate`, `POST /api/ai-effects/import`, `GET /api/ai-effects/export` |
| Generation | `GET /api/generation/stream`, `GET /api/generation/task/{task_id}/status`, `GET /api/generation/modules`, `GET /api/generation/examples`, `GET /api/generation/examples/{module_name}`, history/review/accept/reject |
| Studio | `GET /api/studio/modules`, `POST /api/studio/preview` |
| Notifications | `GET /api/notifications/vapid-public-key`, `GET /api/notifications/subscriptions`, `DELETE /api/notifications/subscriptions/{sub_id}`, `POST /api/notifications/subscribe`, `POST /api/notifications/unsubscribe`, `POST /api/notifications/subscriptions/{sub_id}/test` |
| Debug | `GET /api/debug/log` |
| Metrics | `GET /metrics` |


---

## Health

### `GET /api/health`

Public health check.

Example response:

```json
{
  "status": "ok",
  "version": "0.9.6",
  "auth_enabled": true
}
```

`auth_enabled` tells you whether `APP_ACCESS_TOKEN` is active.

### `GET /api/health/detailed`

Requires authentication.

Checks:
- database
- Immich connectivity
- active AI provider state

---

## Settings

### `GET /api/settings`

Returns the current application settings, including:
- `immich_url`
- AI hourly limits
- `debug_mode`
- `favorite_albums_json`
- `ai_custom_prompt`
- masked API key fields

AI provider and model selection now live on schedules, not in the global settings record.

### `PUT /api/settings`

Rate limit: `10/minute`.

Updates application settings. API keys are stored encrypted. Sending an empty string clears a key.

### AI provider key setup

Use these official vendor docs to create or manage the AI keys DailyFX accepts in the UI:

- [OpenAI API keys](https://platform.openai.com/docs/quickstart)
- [Google AI Studio / Gemini API key](https://ai.google.dev/gemini-api/docs/api-key)
- [OpenRouter API keys](https://openrouter.ai/docs/api-keys)
- [BytePlus access keys](https://docs.byteplus.com/api/docs/byteplus-platform/docs-managing-keys)
- [Xiaomi Cloud-ML quick start](https://docs.api.xiaomi.com/en/cloud-ml/usage/quickstart.html)

For BytePlus AI Image generation, review the available ModelArk models in the
[BytePlus Model Management console](https://console.byteplus.com/ark/region:ark+ap-southeast-1/openManagement).
Some image models expose a free tier or free trial quota there; check the model details and pricing before selecting a model in DailyFX.

### Connection tests

Requires authentication:

- `POST /api/settings/test-immich`
- `POST /api/settings/test-provider/{provider}` (where provider is `openai`, `gemini`, `openrouter`, `byteplus`, `xiaomi`, or `local-ai`)

### `GET /api/settings/models/{provider}`

Returns available models for a given AI provider (e.g. `openai`, `gemini`, `xiaomi`). Used by the Schedule form to dynamically populate model selectors. Falls back to a hardcoded list when the provider API is unreachable.

---

## Immich

Immich domain models live in `backend/app/immich/models.py` and are treated as the single source of truth for search filters, asset/person/album summaries, upload metadata, and EXIF payloads.

`backend/app/schemas/immich.py` is a thin FastAPI adapter layer that converts those domain models into `response_model` classes. The JSON shape exposed by the API stays stable, but the backend no longer duplicates the Immich contract in two places.

### `GET /api/immich/options`

Returns data used by the filter UI:
- albums
- people

### `GET /api/immich/albums`

Returns a paginated list of Immich albums.

Query parameters:
- `page` (integer, default: 1)
- `size` (integer, default: 12)
- `sort_by` (string, one of: `name`, `count`, `created`, `modified`, default: `name`)
- `sort_order` (string, one of: `asc`, `desc`, default: `asc`)

### `GET /api/immich/assets`

Returns a search result page from Immich.

Query parameters:
- `media_type`
- `album_ids`
- `person_ids`
- `person_modes`
- `start_date`
- `end_date`
- `page` (integer, default: 1)
- `size` (integer, default: 24)

### `GET /api/immich/assets/{asset_id}/thumbnail`

Returns a thumbnail image for an asset.

### `GET /api/immich/assets/{asset_id}/exif`

Returns raw EXIF data for an asset as JSON.

The payload keeps the Immich field names used by the rest of the backend and frontend, including camelCase EXIF keys such as `lensModel` and `dateTimeOriginal`.

---

## Presets

All preset endpoints require authentication. Preset creation and updates undergo parameter configuration schema constraint validation.

### Filter presets

- `GET /api/presets/filters`
- `POST /api/presets/filters`
- `PUT /api/presets/filters/{preset_id}`
- `DELETE /api/presets/filters/{preset_id}`

### Effect presets

- `GET /api/presets/effects`
- `POST /api/presets/effects`
- `PUT /api/presets/effects/{preset_id}`
- `DELETE /api/presets/effects/{preset_id}`

Effect presets store a `groups` object that maps generation module names to enabled/weight/config values.

### Notification presets

- `GET /api/presets/notifications`
- `POST /api/presets/notifications`
- `PUT /api/presets/notifications/{preset_id}`
- `DELETE /api/presets/notifications/{preset_id}`
- `POST /api/presets/notifications/{preset_id}/test`

Notification presets accept a comma-separated `provider` list. Supported channels are:

- `web` for browser Web Push subscriptions
- `ntfy` for ntfy topics
- `gotify` for Gotify app notifications
- `telegram` for Telegram Bot messages
- `homeassistant` for Home Assistant notifications
- `slack` for Slack incoming webhooks
- `discord` for Discord webhooks
- `apprise` for Apprise URLs

The response masks secret values and exposes flags such as `has_token`, `token_masked`, and `webhook_url`.

Use `POST /api/presets/notifications/{preset_id}/test` to send a test notification. There is no settings-level notification test endpoint.

---

## Schedules

All schedule endpoints require authentication.

- `GET /api/schedules`
- `POST /api/schedules`
- `PUT /api/schedules/{schedule_id}`
- `DELETE /api/schedules/{schedule_id}`
- `POST /api/schedules/{schedule_id}/run-now`

Schedules combine:
- one filter preset
- one effect preset
- one notification preset
- album name
- optional AI vision/image provider settings

`POST /api/schedules/{schedule_id}/run-now` triggers a selected schedule immediately and returns JSON with `message` and `task_id`. The backend creates a queued history entry right away so the manual run is visible in `GET /api/generation/history` before the worker starts it.

---

## Generation

### `GET /api/generation/stream`

Requires authentication. Server-sent events stream used by the UI for live task/history updates. The stream emits heartbeat events and can request a resync if the client falls too far behind.

### `GET /api/generation/task/{task_id}/status`

Requires authentication. Returns task state, step, progress, timestamps, and error details.

### `GET /api/generation/modules`

Requires authentication. Returns all available generation modules with their labels, descriptions, default weights, and config schemas.

### `GET /api/generation/examples`

Requires authentication. Returns example previews for generation modules.

### `GET /api/generation/examples/{module_name}`

Requires authentication. Returns the generated preview image for one module as `image/png`.

For AI-based generation modules (`ai_*`), the backend may run AI Vision twice during a generation:
- once on the source photo, to help guide prompt enrichment and initial metadata
- once on the final generated image, so the stored title, summary, and tags reflect the image that is actually reviewed and uploaded

For those AI modules, the final-image Vision result wins.

### AI metadata pipeline

The AI metadata flow is easiest to understand as a sequence:

1. The backend selects a source asset from Immich.
2. It builds optional `people_context` from the asset summary when Immich provides people names and, if available, face positions.
3. It runs source-image Vision with that context as a hint.
4. It generates the output image with the selected module.
5. If the module is `ai_*`, it runs Vision again on the generated image.
6. It embeds EXIF, writes the history entry, and stores a `config_json` payload with provenance and trace data.

### History statuses

`GET /api/generation/history` returns `GenerationHistoryResponse` items. The `status` field can now include:

- `QUEUED` for manual schedule runs waiting for the worker
- `RUNNING` for active generation work
- `PENDING_REVIEW` for completed generations awaiting user action
- `UPLOADED`, `REJECTED`, or `FAILED` for finalized outcomes

`people_context` is a hint, not a hard requirement. It can improve source Vision and prompt enrichment when Immich knows people in the source asset, but the pipeline still works when no names or face positions are available.

For a broader view of the backend layers and generation orchestration, see [docs/architecture.md](architecture.md).

The stored `metadata_provenance` object records where the final values came from:
- `title_source`
- `summary_source`
- `tags_source`
- `people_context`
- `source_vision`
- `final_vision`
- `tag_injections`

The `source_vision` and `final_vision` entries include whether the call was attempted, whether it succeeded, and provider/model details. For `ai_*` effects, the final-image Vision result is preferred; if it fails, the backend falls back to the earlier metadata for that run.

The `task_trace` array records the visible run timeline used by the History and review UIs. It is intended for debugging and user-facing progress inspection, not as a replacement for server logs.

### History and review

- `GET /api/generation/history`
- `GET /api/generation/history/{task_id}`
- `GET /api/generation/history/{task_id}/image`
- `POST /api/generation/history/{task_id}/accept`
- `POST /api/generation/history/{task_id}/retry`
- `POST /api/generation/history/{task_id}/reject`
- `DELETE /api/generation/history/rejected`
- `DELETE /api/generation/history/cache`

### `DELETE /api/generation/history/rejected`

Deletes all rejected generations — both the files on disk and the database records. Returns `204` on success.

### `DELETE /api/generation/history/cache`

Deletes all generation history (files + DB records). Returns `204` on success.

Public review endpoints:
- `GET /api/generation/review/{task_id}`
- `GET /api/generation/review/{task_id}/thumbnail`

### `GET /api/generation/stats/effects`

Returns aggregate execution and quality statistics for all photo effects, grouped by effect type. Computes quality scores, ratings mix, and status distributions (uploaded, pending review, rejected/failed). Includes the date of the last run. Used to populate the frontend Statistics dashboard.

`GET /api/generation/history` supports `status`, `search`, `offset`, and `limit`.

The history record includes fields such as:
- `task_id`
- `generation_type`
- `status`
- `title`
- `summary`
- `provider`
- `model`
- `output_path`
- `image_url`
- `album_name`
- `accepted_at`
- `created_at`

For AI-based effects, `title`, `summary`, and `tags_json` are derived from the final generated image when Vision is available. If the final Vision call fails, the backend falls back to the earlier metadata for that run.

The `config_json` payload for each history entry also includes a `metadata_provenance` object that records where each field came from:
- `title_source`
- `summary_source`
- `tags_source`
- `source_vision` and `final_vision` attempt/success details
- `tag_injections` for technical tags such as `AI` and the style label

It may also include a `task_trace` array with the key generation stages and their status/progress, which is what the History and review UIs use for the visible timeline.

---

## Notifications

All notification endpoints require authentication.

- `GET /api/notifications/vapid-public-key`
- `GET /api/notifications/subscriptions`
- `DELETE /api/notifications/subscriptions/{sub_id}`
- `POST /api/notifications/subscribe`
- `POST /api/notifications/unsubscribe`
- `POST /api/notifications/subscriptions/{sub_id}/test`

### `POST /api/notifications/subscriptions/{sub_id}/test`

Sends a test push notification to a specific Web Push subscription. Returns `404` if the subscription is not found.

`POST /api/notifications/subscribe` expects a push subscription payload with fields such as `endpoint`, `p256dh`, `auth`, `device_label`, and `user_agent`.

---

## AI Effects

All AI effects endpoints require authentication. AI effects define reusable prompt-based creative styles that can be assigned to effect presets. Built-in effects come from the seed data; custom effects are user-created.

### `GET /api/ai-effects`

Returns all AI effects, sorted by source (builtin, custom, imported) and title. Hidden built-in effects are excluded.

### `POST /api/ai-effects`

Creates a new custom AI effect.

Request body:
- `id` (string, required) — unique identifier
- `title` (string, required)
- `description` (string, required)
- `display_group` (string, optional)
- `positive_prompt` (string, required)
- `negative_prompt` (string, optional)
- `custom_prompt_placeholder` (string, optional)
- `enabled` (boolean, required)

Returns `409` if the `id` already exists.

### `PUT /api/ai-effects/{effect_id}`

Updates an existing AI effect. Built-in effects can be edited; changes are tracked with `user_modified_at`.

### `DELETE /api/ai-effects/{effect_id}`

Deletes a custom AI effect. Built-in effects are disabled instead of deleted. Returns `409` if the effect is referenced by an effect preset.

### `POST /api/ai-effects/{effect_id}/reset`

Resets a built-in AI effect to its seed defaults. Only works for effects with `source == "builtin"`. Returns `409` otherwise.

### `POST /api/ai-effects/{effect_id}/duplicate`

Creates a copy of an existing AI effect with a `_copy` suffix appended to the ID. The copy has `source == "custom"`.

### `POST /api/ai-effects/import`

Imports AI effects from a JSON payload. Accepts:
- `effects` (array of effect objects)
- `overwrite_existing` (boolean) — if `true`, existing effects are updated; otherwise conflicts are reported.

Returns a result object with `added`, `updated`, and `conflicts` arrays.

### `GET /api/ai-effects/export`

Exports all AI effects as a JSON payload suitable for import (includes `schema_version` and `effects` array).

---

## Studio

All studio endpoints require authentication.

### `GET /api/studio/modules`

Returns all compatible single-source creative modules supported by the studio page.

### `POST /api/studio/preview`

Rate limit: `5/minute`.

Validates the submitted effect configuration against its schema and applies the creative filter to a locally uploaded image (`file`). Generates a temporary rendering session under the `data/temp/studio` workspace, commits a pending review entry into the database history, and returns the newly generated `task_id` along with image URLs.

---

## Metrics

### `GET /metrics`

Prometheus-compatible application metrics. Requires authentication if `APP_ACCESS_TOKEN` is configured.

Exposes:
- `dailyfx_app_info`: Application metadata (e.g., version).
- `dailyfx_generation_task_status`: Count of active/queued generation tasks by status (`queued`, `running`, `completed`, `failed`).
- `dailyfx_generation_history_status`: Count of historical generation tasks by status (`pending_review`, `accepted`, `rejected`, `failed`).
- `dailyfx_scheduler_heartbeat_age_seconds`: Time in seconds since the last scheduler heartbeat (based on the modification age of the `scheduler.health` file).

Example response (Prometheus exposition format):

```text
# HELP dailyfx_app_info Application metadata.
# TYPE dailyfx_app_info gauge
dailyfx_app_info{version="0.9.6"} 1
# HELP dailyfx_generation_task_status Count of active/queued generation tasks by status.
# TYPE dailyfx_generation_task_status gauge
dailyfx_generation_task_status{status="queued"} 0
dailyfx_generation_task_status{status="running"} 0
dailyfx_generation_task_status{status="completed"} 0
dailyfx_generation_task_status{status="failed"} 0
# HELP dailyfx_generation_history_status Count of historical generation tasks by status.
# TYPE dailyfx_generation_history_status gauge
dailyfx_generation_history_status{status="pending_review"} 1
dailyfx_generation_history_status{status="accepted"} 5
dailyfx_generation_history_status{status="rejected"} 0
dailyfx_generation_history_status{status="failed"} 0
# HELP dailyfx_scheduler_heartbeat_age_seconds Time in seconds since last scheduler heartbeat.
# TYPE dailyfx_scheduler_heartbeat_age_seconds gauge
dailyfx_scheduler_heartbeat_age_seconds 12
```

---

## Debug

### `GET /api/debug/log`

Returns the latest debug log as `text/plain`. Treat this endpoint as diagnostic-only.

---

## Practical notes

- `POST /api/schedules/{schedule_id}/run-now` starts work asynchronously and returns a `task_id`.
- There is no separate manual `/api/generation/run-now` endpoint anymore; manual triggering happens from the Schedules UI against a chosen schedule.
- The public review endpoints are intended for the web UI and notifications.
- If you want the backend layer map instead of endpoint details, start with [docs/architecture.md](architecture.md).
