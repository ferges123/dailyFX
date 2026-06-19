# Accessibility (A11y) Improvements Design

This document details the accessibility improvements to be made in the DailyFX frontend to resolve the accessibility issues identified in the audit report.

## Target Gaps

1. **Modals Close Buttons:** Missing `aria-label` on close buttons in `ConfirmModal.tsx`, `UploadModal.tsx`, and `ConfirmDeleteModal.tsx`.
2. **Modal Context:** Missing `role="dialog"` and `aria-modal="true"` on the outer container of all modals (`ConfirmModal`, `UploadModal`, `ConfirmDeleteModal`, and `LightboxModal`).
3. **Form Controls:** Missing descriptive label on search and filter elements in `HistoryPage.tsx`.
4. **Dynamic Alerts:** Missing live announcement when saving configuration in `Settings.tsx`.

## Proposed Solution (Approach A)

### 1. Modals (`ConfirmModal`, `ConfirmDeleteModal`, `UploadModal`, `LightboxModal`)
* Set `role="dialog"` and `aria-modal="true"` on the primary dialog containers.
* Use `aria-labelledby` linking to the dialog's header title elements to provide screen readers with context on modal opening.
* Set `aria-label="Close"` on the close buttons.

### 2. Search & Filters (`HistoryPage`)
* Add `aria-label="Search history"` to the search input.
* Add `aria-label="Filter history by status"` to the filter dropdown.

### 3. Dynamic Alerts (`Settings`)
* Wrap the dynamic save success/error status messages inside an outer `div` container having `aria-live="polite"` to ensure consistent reading of updates across assistive technologies.
