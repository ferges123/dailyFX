# Task List

| Task | Status | Description |
|---|---|---|
| Create A11y Unit Tests | done | Create unit tests to verify the accessibility attributes for modals, form inputs, and dynamic status message. |
| Implement Modal Accessibility Attributes | done | Update ConfirmModal, ConfirmDeleteModal, UploadModal, and LightboxModal with accessibility roles and attributes. |
| Implement HistoryPage Controls Accessibility | done | Add aria-labels to the search input and the status select filter in HistoryPage.tsx. |
| Implement Settings Saved Message Live Announcement | done | Wrap dynamic success/error status messages in Settings.tsx with an aria-live="polite" container. |
| Verify and build | done | Run all unit tests, linters, formatting, and Vite build to confirm correctness. |
| Fix frontend build failure | done | Investigate and fix the frontend build failure (vulnerability in undici) |
| Fix N+1 queries in list_people | done | Optimize list_people endpoint of Immich client to remove N+1 statistics calls |
| Implement HTTP connection pooling | done | Cache and reuse httpx.AsyncClient instances to support connection pooling |
| Optimize duplicate list_albums | done | Reuse returned value of create_album in routes_generation to avoid duplicate list_albums call |
| Split large frontend files | done | Split HistoryDetailPanel.tsx and Schedules.tsx into smaller sub-components |
