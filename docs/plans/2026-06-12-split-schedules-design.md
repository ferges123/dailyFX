# Design Document: Split Schedules.tsx (Task 5)

## 1. Overview
The `Schedules.tsx` file is currently over 1300 lines of code, combining page layouts, business logic, summary widgets, and a complex schedule creation/editing form. This document specifies the design for splitting it into smaller, modular, and maintainable components under the `frontend/src/pages/Schedules/` folder.

## 2. Component Architecture
We will decompose `Schedules.tsx` as follows:

### 2.1 shared Types and Defaults (`frontend/src/pages/Schedules/types.ts`)
* Move `FormState` and `emptyForm` to this file.

### 2.2 Summary Card Widget (`frontend/src/pages/Schedules/ScheduleSummaryCard.tsx`)
* Extract `ScheduleSummaryCard` component.

### 2.3 Schedule Editing/Creation Form (`frontend/src/pages/Schedules/ScheduleForm.tsx`)
* Extract the entire form panel (`<aside aria-label="Schedule form panel">`).
* The form component will accept props for form state, configuration options, loading states, presets data, validation errors, and event callback handers:
  - `form`: `FormState`
  - `setForm`: `React.Dispatch<React.SetStateAction<FormState>>`
  - `isNew`: `boolean`
  - `editingName`: `string | undefined`
  - `validationIssues`: `string[]`
  - `canSave`: `boolean`
  - `isSaving`: `boolean`
  - `onSave`: `() => void`
  - `onCancel`: `() => void`
  - `filterPresets`: `any[]`
  - `effectPresets`: `any[]`
  - `notificationPresets`: `any[]`

### 2.4 Main Page Layout (`frontend/src/pages/Schedules.tsx`)
* Keep `SchedulesPage` (exported by `Schedules.tsx`) as the main container page managing query loading, search filtering, and mutation execution.
* Import `ScheduleSummaryCard` and `ScheduleForm` from the `Schedules/` subdirectory.

## 3. Verification and Testing
* Run `npm run test` (vitest) to verify that all existing tests in `frontend/src/__tests__/Schedules.test.tsx` pass without regressions.
