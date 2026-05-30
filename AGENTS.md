# Repository Guidelines

## Project Structure & Module Organization
- `frontend/` contains the Vite + React UI. Main code lives in `frontend/src/`, with pages in `frontend/src/pages/`, shared components in `frontend/src/components/`, and API helpers in `frontend/src/api/`.
- Frontend tests live in `frontend/src/__tests__/`.
- `backend/` contains the FastAPI service.
- `tests/filter-showcase/` holds image fixtures for filter validation.
- Runtime files are written to `data/`, including `data/app.db` and generated results.

## Build, Test, and Development Commands
- `docker compose up --build -d` starts the full stack locally.
- `cd frontend && npm run dev` runs the UI on `http://localhost:8439`.
- `cd frontend && npm run build` type-checks and builds the frontend.
- `cd frontend && npm test` runs the Vitest suite once; `npm run test:watch` keeps it running.
- `make backend-install` installs backend dependencies with test extras.
- `make backend-test` runs `python3 -m pytest`.

## Coding Style & Naming Conventions
- Follow existing TypeScript/React patterns in `frontend/src/`. Use `PascalCase` for components and descriptive lowercase filenames for utilities.
- Keep 2-space indentation, single quotes, and trailing commas where the formatter uses them.
- Python code in `backend/` should follow standard FastAPI and `pytest` conventions.

## Testing Guidelines
- Frontend tests use Vitest with Testing Library; name them by behavior, such as `History.test.tsx`.
- Backend tests are discovered from `backend/tests/` via `pytest`.
- Prefer focused tests for UI states, API errors, and generation flows.

## Commit & Pull Request Guidelines
- This checkout has no Git commit history yet, so no convention is established. Use short, imperative subjects with a narrow scope, for example `frontend: fix login loading state`.
- Pull requests should summarize the change, note config or migration impact, and include screenshots for UI changes.
- Call out test coverage explicitly when touching generation logic, auth, or persistence.

## Security & Configuration Tips
- Keep secrets in `.env`; never commit API keys, tokens, or generated database files.
- `APP_SECRET_KEY`, `IMMICH_URL`, and `IMMICH_API_KEY` are required for a working local setup.
- Treat `data/` as persistent runtime state.
