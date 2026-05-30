# Frontend Documentation

## Overview
The frontend is a Vite + React + TypeScript single-page app that talks only to the backend API. It provides the operator UI for reviewing generated images, configuring presets, scheduling jobs, and managing settings.

## Main Screens
- `History`: review generated results, search by title/summary/provider, inspect metadata, and accept, reject, retry, or download images.
- `Schedules`: create and edit automated jobs by combining filter presets, effect presets, notification presets, and AI vision/image provider settings.
- `Presets`: manage filter presets, effect presets, notification presets, and web push subscriptions.
- `Settings`: configure Immich access, API keys, AI budgets, and the default AI prompt.
- `Login`: shown only when `APP_ACCESS_TOKEN` is enabled on the backend.

## Data Flow
- The app fetches most data through `/api/*` endpoints defined in [frontend/src/api/client.ts](../frontend/src/api/client.ts).
- Authentication uses a bearer token stored in `localStorage` under `dailyfx_token`.
- The history view also listens to `/api/generation/stream` for live status updates.
- Images are loaded through authenticated fetches via `SecureImage`, so protected instances still work without exposing raw image URLs.

## Browser State
- `localStorage`: access token, cached Immich filter options, filter presets, and other UI cache entries.
- `sessionStorage`: last started generation task ID for the history view.
- Cookie: app-level filter state used by the preset/filter UI.
- Service worker: `frontend/public/sw.js` enables web push notifications.

## Frontend Structure
- `frontend/src/App.tsx`: shell layout, mobile navigation, and view switching.
- `frontend/src/pages/`: page-level screens and helpers.
- `frontend/src/components/`: reusable UI controls and image handling.
- `frontend/src/api/`: typed API client and auth helpers.

## Development
- `cd frontend && npm run dev` starts the UI on port `8439`.
- `cd frontend && npm run build` type-checks and builds production assets.
- `cd frontend && npm test` runs the Vitest suite.

## Deployment Notes
- The frontend is served by nginx in the `web` container.
- `VITE_API_BASE_URL` can be used to point the UI at a non-default backend URL if you host the frontend separately.
- When you use the default `docker compose` setup, leave `VITE_API_BASE_URL` unset and let nginx proxy `/api/*` to the backend.
- If backend auth is enabled, the login token must match `APP_ACCESS_TOKEN`.
