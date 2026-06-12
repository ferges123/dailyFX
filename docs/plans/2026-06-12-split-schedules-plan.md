# Split Schedules.tsx Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Refactor `Schedules.tsx` by splitting it into smaller components in the `frontend/src/pages/Schedules/` folder.

**Architecture:** Create `types.ts`, `ScheduleSummaryCard.tsx`, and `ScheduleForm.tsx` components. Refactor `Schedules.tsx` to import and use them.

**Tech Stack:** React, TypeScript.

---

### Task 1: Create shared types and default state

**Files:**
- Create: `frontend/src/pages/Schedules/types.ts`

**Step 1: Write code**
Implement `FormState` and `emptyForm` in `frontend/src/pages/Schedules/types.ts`.

**Step 2: Commit**
```bash
git add frontend/src/pages/Schedules/types.ts
git commit -m "refactor: extract Schedules types and default state"
```

---

### Task 2: Extract ScheduleSummaryCard component

**Files:**
- Create: `frontend/src/pages/Schedules/ScheduleSummaryCard.tsx`

**Step 1: Write code**
Implement `ScheduleSummaryCard` in `frontend/src/pages/Schedules/ScheduleSummaryCard.tsx`.

**Step 2: Commit**
```bash
git add frontend/src/pages/Schedules/ScheduleSummaryCard.tsx
git commit -m "refactor: extract ScheduleSummaryCard component"
```

---

### Task 3: Extract ScheduleForm component

**Files:**
- Create: `frontend/src/pages/Schedules/ScheduleForm.tsx`

**Step 1: Write code**
Implement `ScheduleForm` in `frontend/src/pages/Schedules/ScheduleForm.tsx`, passing form states, presets, callbacks, and validation issues.

**Step 2: Commit**
```bash
git add frontend/src/pages/Schedules/ScheduleForm.tsx
git commit -m "refactor: extract ScheduleForm component"
```

---

### Task 4: Refactor Schedules.tsx to use split components

**Files:**
- Modify: `frontend/src/pages/Schedules.tsx`

**Step 1: Write code**
Update `frontend/src/pages/Schedules.tsx` to import the new components and remove the extracted code.

**Step 2: Verification**
Run frontend tests: `cd frontend && npm run test`
Expected: PASS (all 51 tests pass successfully).

**Step 3: Commit**
```bash
git add frontend/src/pages/Schedules.tsx
git commit -m "refactor: use split components in SchedulesPage"
```
