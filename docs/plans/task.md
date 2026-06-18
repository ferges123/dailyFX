# Live Tracker: Repository Improvements

| Task | Status | Details |
| :--- | :--- | :--- |
| Comprehensive Audit | Done | Documented at [2026-06-18-comprehensive-audit.md](file:///opt/dailyFX/docs/plans/2026-06-18-comprehensive-audit.md) |
| Add missing .gitignore entries | Done | Added at end of root `.gitignore` |
| Add engines to package.json | Done | Added constraint `"engines"` in `frontend/package.json` |
| Add CSP meta tag | Done | Added meta tag in `<head>` in `frontend/index.html` |
| Add aria-label to mobile & desktop nav | Done | Added `aria-label` to sidebar and bottom nav elements in `frontend/src/App.tsx` |
| Add outside-click handler to AIEffectCard dropdown | Done | Added handler using `useRef` and `useEffect` event listener in `frontend/src/pages/AIEffects/AIEffectCard.tsx` |
| Add tests (modals, form submits, AIEffects CRUD) | Done | Created integration test file `frontend/src/__tests__/AIEffects.test.tsx` and verified all 61 tests pass |
| Add SAST (bandit) to CI | Done | Added `bandit` dependency in `backend/pyproject.toml` and job step in `.github/workflows/ci.yml` |
