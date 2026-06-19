# Task List

| Task | Status | Description |
|---|---|---|
| Refactor helper functions in HistoryDetailPanel.tsx | done | Move formatVisionState, formatElapsed, and formatDuration outside the HistoryDetailPanel component definition. |
| Wrap reusable components in React.memo | done | Wrap SecureImage, StatusTile, Field, SelectField, UploadModal, LightboxModal, and HistoryDetailPanel in React.memo (or memo). |
| Extract and memoize list item card in HistoryPage.tsx | done | Extract the inline list item rendering in HistoryPage.tsx into a memoized HistoryItemCard component. |
| Memoize callbacks with useCallback in HistoryPage.tsx | done | Wrap all inline handlers/callbacks in HistoryPage.tsx (e.g. handleRefreshAll, onBackToList, onAccept, etc.) in useCallback. |
| Memoize JSON.parse calls in HistoryDetailPanel.tsx | done | Wrap JSON.parse calls in HistoryDetailPanel.tsx around lines 74-103 in useMemo hooks. |
| Add blob URL caching to SecureImage.tsx | done | Introduce a simple global cache for fetched blob URLs in SecureImage.tsx to avoid refetching same images. |
| Consolidated duplicate dataclasses in backend | done | Consolidated GenerationModuleSelection and GenerationArtifacts into pipeline/shared.py and imported them in engine.py. |
| Removed duplicate helper functions in engine.py | done | Removed duplicate implementations of _failed_history_provider and delegated _merge_module_defaults in pipeline/planning.py. |
| Consolidated try-except blocks for Immich exceptions | done | Created handle_immich_errors context manager in app/immich/errors.py and refactored API routes. |
| Unified file and database deletion logic in routes_generation.py | done | Replaced duplicate history purge and output path file unlinking with _delete_history_records_and_files helper. |
| Validate path traversal in routes_generation.py | done | Validate output_path retrieved from database to prevent path traversal in routes_generation.py:327-329. |
| Fix wide except Exception in token verification | done | Narrow exception handling or log security errors in security.py:80 instead of silently swallowing them. |
| Synchronize frontend and backend versions | done | Sync version string (0.3.20) in backend (e.g. version/health endpoint) and version.ts, App.tsx, Settings.tsx. |
| Verify and build | done | Run tests, formatting, and linters for frontend and backend to verify correctness. |
