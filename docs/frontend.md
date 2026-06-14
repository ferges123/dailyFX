# Frontend Documentation

## Overview
The frontend is a modern single-page application (SPA) that communicates with the backend API. It provides the operator interface for reviewing generated images, configuring presets, scheduling automation jobs, and managing settings.

## Tech Stack
The frontend has been upgraded to the following modern technologies:
- **Core Framework**: React 19
- **Build System**: Vite 8 (utilizing the Rolldown/Oxc based compiler under the hood for extremely fast builds)
- **Programming Language**: TypeScript 6
- **Styling**: Tailwind CSS v4.3 (leveraging the new CSS-first configuration system in [styles.css](../frontend/src/styles.css) instead of `tailwind.config.js` or PostCSS configurations)
- **Data Fetching & Caching**: TanStack React Query v5.101.0
- **Testing**: Vitest 4.1.8 with React Testing Library and JSDOM
- **Icons**: Lucide React v1.17.0
- **Progressive Web App (PWA)**: vite-plugin-pwa (Vite plugin to automate service worker building and manifest injection)

## Main Screens
- `History`: review generated results, see queued and running schedule runs, search by title/summary/provider, inspect metadata, and accept, reject, retry, or download images. Supports dynamic **Before/After Image Comparison** toggles (switching between the original photo and the styled AI result) in both the details panel and the full-screen lightbox view.
- `Schedules`: create and edit automated jobs by combining filter presets, effect presets, notification presets, and AI vision/image provider settings.
- `Presets`: manage filter presets, effect presets, notification presets, and web push subscriptions.
- `Studio`: upload a local photo, select a compatible single-source effect, configure parameters, view a live generation preview, and persist it to history. Features drag-and-drop file ingestion and a memory-safe source image thumbnail preview.
- `Settings`: configure Immich access, API keys, AI budgets, and the default AI prompt.
- `Login`: shown only when `APP_ACCESS_TOKEN` is enabled on the backend.

## Data Flow
- The app fetches most data through `/api/*` endpoints defined in [frontend/src/api/client.ts](../frontend/src/api/client.ts).
- Authentication uses a bearer token stored in `localStorage` under `dailyfx_token`.
- The history view also listens to `/api/generation/stream` for live status updates, including queued and running run-now tasks.
- Images are loaded through authenticated fetches via `SecureImage`, so protected instances still work without exposing raw image URLs.

## Browser State
- `localStorage`: access token, cached Immich filter options, filter presets, and other UI cache entries.
- `sessionStorage`: last started generation task ID for the history view.
- Cookie: app-level filter state used by the preset/filter UI.
- Service worker: `frontend/src/sw.js` (compiled to `dist/sw.js` via `vite-plugin-pwa`) enables both PWA offline shell assets caching (precaching) and web push notifications.

## Frontend Structure
- `frontend/src/App.tsx`: shell layout, mobile navigation, route definition with lazy loading, and view switching.
- `frontend/src/pages/`: page-level screens and helpers.
  - `History/`: contains `HistoryPage` and related details/lightbox controls.
  - `Presets/`: modular split of tabs (`EffectPresetsPage.tsx`, `FilterPresetsPage.tsx`, `NotificationPresetsPage.tsx`) under a common `PresetHeader`.
  - `Schedules/`: split of form details (`ScheduleForm.tsx`, `ScheduleSummaryCard.tsx`) to improve maintainability.
  - `Settings/`: contains configuration sections (`AIProviderSettingsSection.tsx`, `ConnectionTestsSection.tsx`, `RuntimeStatusSection.tsx`) and settings validation helpers.
- `frontend/src/components/`: reusable UI controls and image handling.
  - `RouteErrorBoundary.tsx`: route-level boundary displaying localized error UI instead of crashing the app shell.
- `frontend/src/api/`: typed API client and auth helpers.
- `frontend/src/version.ts`: single source of truth for the application version, imported by the desktop sidebar and mobile settings footer.

## Application Reliability
- **Lazy Loading**: Route-level components are imported dynamically via `React.lazy()` and wrapped in `Suspense` with a graceful loading fallback to optimize bundle size.
- **Error Boundaries**: Every page view is wrapped in a `RouteErrorBoundary` component. This prevents UI-level JavaScript runtime failures on one page from taking down the entire application workspace.

## Development
- `cd frontend && npm run dev` starts the UI on port `8439`.
- `cd frontend && npm run build` type-checks and builds production assets.
- `cd frontend && npm test` runs the Vitest suite.

## Deployment Notes
- The frontend is served by nginx in the `web` container.
- `VITE_API_BASE_URL` can be used to point the UI at a non-default backend URL if you host the frontend separately.
- When you use the default `docker compose` setup, leave `VITE_API_BASE_URL` unset and let nginx proxy `/api/*` to the backend.
- If backend auth is enabled, the login token must match `APP_ACCESS_TOKEN`.
