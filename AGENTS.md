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
- `make backend-lint` runs `ruff check .` in the backend directory.
- `make backend-format` runs `ruff format .` in the backend directory.

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
- **NEVER** track, stage, commit, or push files under `docs/plans/` (e.g., `task.md`, `AUDIT_REPORT.md`) to Git/GitHub.


## Versioning & Release Rules
- Always use standard Semantic Versioning (SemVer) with three segments: `MAJOR.MINOR.PATCH` (e.g. `0.1.0` is standard and preferred over non-standard `0.01` or `0.0.1` when introducing new features).
- The version must be bumped (following SemVer) whenever code changes are made and a new Docker image is built.
- Maintain the version string in `frontend/package.json`, `frontend/src/App.tsx` (desktop sidebar), and `frontend/src/pages/Settings.tsx` (mobile footer).

## Host-Side Agent Execution (dailyfx-agent)
- When invoked on the host via `dailyfx-agent` (using targets like `agy` or `codex`), the agent must perform both **Source Vision** (analyzing the input image for context/people) and **Final Vision** (analyzing the final generated image for what actually appears in it).
- The agent must use these vision steps to generate a high-quality title and summary, and then write/update these values in the local JSON manifest file (e.g. `data/dailyfx-run.json` or as specified by the command-line arguments) under the `title` and `summary` keys before exiting. This ensures the backend receives the enriched metadata during the finalization step.

