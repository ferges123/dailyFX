# Contributing

Thanks for helping improve DailyFX for immich.

## Before opening a PR

- Keep changes focused and small.
- Run the relevant test suite locally.
- Update `README.md` or `docs/` when behavior changes.
- Do not commit local runtime data from `data/`, `.env`, or generated artifacts.

## Recommended checks

- Backend: `cd backend && pytest`
- Backend lint: `make backend-lint`
- Backend format: `make backend-format`
- Frontend: `cd frontend && npm test && npm run build`

## Reporting issues

Include:

- What you expected to happen
- What actually happened
- Relevant logs or screenshots
- Your environment details, if the issue is environment-specific
