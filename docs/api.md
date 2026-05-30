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

- Rate limit: `120/minute` per client IP
- Errors are returned as JSON with a `detail` field
- Some endpoints return binary content such as PNG, JPEG, HTML, or plain text

## Endpoint Map

| Area | Endpoints |
|---|---|
| Health | `GET /api/health`, `GET /api/health/detailed` |
| Settings | `GET /api/settings`, `PUT /api/settings`, `POST /api/settings/test-immich`, `POST /api/settings/test-openai`, `POST /api/settings/test-gemini`, `POST /api/settings/test-openrouter`, `POST /api/settings/test-byteplus`, `POST /api/settings/test-xiaomi` |
| Immich | `GET /api/immich/options`, `GET /api/immich/assets`, `GET /api/immich/assets/{asset_id}/thumbnail`, `GET /api/immich/assets/{asset_id}/exif` |
| Presets | CRUD for `filters`, `effects`, `notifications` |
| Schedules | CRUD plus `POST /api/schedules/{schedule_id}/run-now` |
| Generation | `GET /api/generation/stream`, `GET /api/generation/task/{task_id}/status`, `GET /api/generation/modules`, `GET /api/generation/examples`, `GET /api/generation/examples/{module_name}`, history/review/accept/reject |
| Notifications | `GET /api/notifications/vapid-public-key`, `GET /api/notifications/subscriptions`, `DELETE /api/notifications/subscriptions/{sub_id}`, `POST /api/notifications/subscribe`, `POST /api/notifications/unsubscribe` |
| Debug | `GET /api/debug/log` |

---

## Health

### `GET /api/health`

Public health check.

Example response:

```json
{
  "status": "ok",
  "version": "0.1.0",
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

Updates application settings. API keys are stored encrypted. Sending an empty string clears a key.

### Connection tests

Requires authentication:

- `POST /api/settings/test-immich`
- `POST /api/settings/test-openai`
- `POST /api/settings/test-gemini`
- `POST /api/settings/test-openrouter`
- `POST /api/settings/test-byteplus`
- `POST /api/settings/test-xiaomi`

---

## Immich

Immich domain models live in `backend/app/immich/models.py` and are treated as the single source of truth for search filters, asset/person/album summaries, upload metadata, and EXIF payloads.

`backend/app/schemas/immich.py` is a thin FastAPI adapter layer that converts those domain models into `response_model` classes. The JSON shape exposed by the API stays stable, but the backend no longer duplicates the Immich contract in two places.

### `GET /api/immich/options`

Returns data used by the filter UI:
- albums
- people

### `GET /api/immich/assets`

Returns a search result page from Immich.

Query parameters:
- `media_type`
- `album_ids`
- `person_ids`
- `person_modes`
- `start_date`
- `end_date`

### `GET /api/immich/assets/{asset_id}/thumbnail`

Returns a thumbnail image for an asset.

### `GET /api/immich/assets/{asset_id}/exif`

Returns raw EXIF data for an asset as JSON.

The payload keeps the Immich field names used by the rest of the backend and frontend, including camelCase EXIF keys such as `lensModel` and `dateTimeOriginal`.

---

## Presets

All preset endpoints require authentication.

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

Notification presets accept a comma-separated `provider` list such as `web`, `ntfy`, `gotify`, `telegram`, and `homeassistant`.

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

`POST /api/schedules/{schedule_id}/run-now` triggers a selected schedule immediately and returns JSON with `message` and `task_id`.

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

Public review endpoints:
- `GET /api/generation/review/{task_id}`
- `GET /api/generation/review/{task_id}/thumbnail`

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

`POST /api/notifications/subscribe` expects a push subscription payload with fields such as `endpoint`, `p256dh`, `auth`, `device_label`, and `user_agent`.

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
