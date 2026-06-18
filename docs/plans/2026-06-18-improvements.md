# Repository Improvements Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Improve codebase configuration, accessibility, safety, test coverage, and automated static security analysis.

**Architecture:** Standard updates to config files, adding a custom React hooks/effects for outside dropdown clicks, introducing an integration test file for `AIEffectsPage`, and updating CI files.

**Tech Stack:** Node.js, React, Vitest, Python, Bandit SAST.

### Task 0: Comprehensive Audit

**Files:**
- Create: `docs/plans/2026-06-18-comprehensive-audit.md`

**Status:** Done (Documented at [2026-06-18-comprehensive-audit.md](file:///opt/dailyFX/docs/plans/2026-06-18-comprehensive-audit.md))

---

### Task 1: Add Missing .gitignore Entries

**Status:** Done

**Files:**
- Modify: `/.gitignore`

**Step 1: Add entries to `.gitignore`**
Add the following lines at the end of `/.gitignore`:
```
.vscode/
.idea/
.DS_Store
Thumbs.db
```

**Step 2: Verify git status ignores these**
Expected: Git status is clean and does not track these directories.

**Step 3: Commit**
```bash
git add .gitignore
git commit -m "chore: add editor and OS system files to gitignore"
```

---

### Task 2: Add engines to package.json

**Status:** Done

**Files:**
- Modify: `/frontend/package.json`

**Step 1: Add engines section to `package.json`**
Add the `"engines"` configuration right after `"type": "module"` in `frontend/package.json`:
```json
  "engines": {
    "node": ">=22.0.0",
    "npm": ">=10.0.0"
  },
```

**Step 2: Format package.json**
Run `cd frontend && npm run format` to ensure style/indentation constraints are satisfied.

**Step 3: Commit**
```bash
git add frontend/package.json
git commit -m "chore: add node and npm engine constraints to package.json"
```

---

### Task 3: Add CSP Meta Tag

**Status:** Done

**Files:**
- Modify: `/frontend/index.html`

**Step 1: Add the CSP meta tag**
Insert the following tag inside `<head>` in `/frontend/index.html`:
```html
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'self';" />
```

**Step 2: Commit**
```bash
git add frontend/index.html
git commit -m "security: add Content-Security-Policy meta tag to frontend index.html"
```

---

### Task 4: Add Navigation `aria-label`

**Status:** Done

**Files:**
- Modify: `/frontend/src/App.tsx`

**Step 1: Add `aria-label` attributes to navigation elements**
Add `aria-label="Desktop navigation"` to the sidebar nav around line 166:
```tsx
        <nav aria-label="Desktop navigation" className="mt-8 grid gap-1.5">
```
Add `aria-label="Mobile navigation"` to the mobile bottom nav around line 340:
```tsx
      <nav aria-label="Mobile navigation" className="fixed bottom-0 left-0 right-0 z-20 flex items-center justify-around border-t border-white/70 bg-[rgba(248,246,239,0.88)] px-2 py-1.5 shadow-[0_-8px_30px_rgba(36,29,16,0.08)] backdrop-blur-xl md:hidden">
```

**Step 2: Commit**
```bash
git add frontend/src/App.tsx
git commit -m "accessibility: add aria-label attributes to desktop and mobile navigation elements"
```

---

### Task 5: Add Outside-Click Handler to AIEffectCard Dropdown

**Status:** Done

**Files:**
- Modify: `/frontend/src/pages/AIEffects/AIEffectCard.tsx`

**Step 1: Add useRef and useEffect click listener**
Update imports:
```typescript
import { useState, useEffect, useRef } from 'react';
```
Create a `useRef<HTMLDivElement>(null)` and attach a `mousedown` event listener inside `useEffect` inside `AIEffectCard` component:
```typescript
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setShowActions(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);
```
Bind the `ref` to the outer div surrounding the action buttons:
```tsx
        <div ref={dropdownRef} className="relative flex flex-wrap gap-1.5 sm:justify-end">
```

**Step 2: Commit**
```bash
git add frontend/src/pages/AIEffects/AIEffectCard.tsx
git commit -m "feat: add click-outside handler to AIEffectCard dropdown menu"
```

---

### Task 6: Add AI Effects CRUD and Modal tests

**Status:** Done

**Files:**
- Create: `/frontend/src/__tests__/AIEffects.test.tsx`

**Step 1: Implement test file `frontend/src/__tests__/AIEffects.test.tsx`**
Create a comprehensive test suite including:
1. Listing effects and filtering.
2. Clicking "New effect", validation failure showing warnings, filling fields, and saving (creating custom effect via `createAIEffect`).
3. Clicking "Edit effect", modifying fields, and saving via `updateAIEffect`.
4. Triggering the more actions dropdown menu, verifying outside clicks reset `showActions` (if possible to test), clicking duplicate, showing the duplicate confirmation modal, confirming, and checking `duplicateAIEffect` API call.
5. Clicking reset on a built-in effect, showing the reset confirmation modal, confirming, and checking `resetAIEffect` API call.
6. Clicking delete, showing delete modal, confirming, and checking `deleteAIEffect` API call.

Code to write in `/frontend/src/__tests__/AIEffects.test.tsx`:
```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { AIEffectsPage } from '../pages/AIEffects';
import * as client from '../api/client';

vi.mock('../api/client', async () => {
  const actual = await vi.importActual('../api/client');
  return {
    ...actual,
    getAIEffects: vi.fn(),
    createAIEffect: vi.fn(),
    updateAIEffect: vi.fn(),
    deleteAIEffect: vi.fn(),
    duplicateAIEffect: vi.fn(),
    resetAIEffect: vi.fn(),
    exportAIEffects: vi.fn(),
    importAIEffects: vi.fn(),
  };
});

const mockEffects = [
  {
    id: 'portrait_classic',
    title: 'Portrait Classic',
    description: 'Classic portrait enhancement.',
    display_group: 'Portrait',
    positive_prompt: 'enhancing portrait',
    negative_prompt: 'blurry',
    custom_prompt_placeholder: null,
    enabled: true,
    hidden: false,
    source: 'builtin',
    builtin_hash: 'hash1',
    latest_builtin_hash: 'hash1',
    user_modified_at: null,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 'illustration_comic',
    title: 'Comic Illustration',
    description: 'Turn image into a comic style.',
    display_group: 'Illustration',
    positive_prompt: 'comic book style',
    negative_prompt: 'realistic',
    custom_prompt_placeholder: 'superhero style',
    enabled: true,
    hidden: false,
    source: 'custom',
    builtin_hash: null,
    latest_builtin_hash: null,
    user_modified_at: null,
    created_at: '2026-06-02T00:00:00Z',
    updated_at: '2026-06-02T00:00:00Z',
  }
];

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AIEffectsPage />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe('AIEffectsPage CRUD and Modals', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.getAIEffects).mockResolvedValue(mockEffects);
  });

  it('renders standard layout and filter options', async () => {
    renderPage();
    expect(await screen.findByText('Portrait Classic')).toBeInTheDocument();
    expect(screen.getByText('Comic Illustration')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'AI effects group filter' })).toBeInTheDocument();
  });

  it('handles creating a custom AI effect and validation issues', async () => {
    vi.mocked(client.createAIEffect).mockResolvedValue({
      id: 'custom_retro',
      title: 'Retro Style',
      description: 'Retro look',
      display_group: 'Artistic',
      positive_prompt: 'vintage colors',
      negative_prompt: 'modern',
      custom_prompt_placeholder: null,
      enabled: true,
      hidden: false,
      source: 'custom',
      builtin_hash: null,
      latest_builtin_hash: null,
      user_modified_at: null,
      created_at: '2026-06-18T00:00:00Z',
      updated_at: '2026-06-18T00:00:00Z',
    });

    renderPage();

    const newBtn = await screen.findByRole('button', { name: /New effect/i });
    fireEvent.click(newBtn);

    // Fail first: Empty form submit
    const saveBtn = screen.getByRole('button', { name: /Save/i });
    expect(saveBtn).toBeDisabled(); // Save button starts disabled due to validation requirements

    // Fill form
    fireEvent.change(screen.getByLabelText(/ID/i), { target: { value: 'custom_retro' } });
    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: 'Retro Style' } });
    fireEvent.change(screen.getByLabelText(/Positive prompt/i), { target: { value: 'vintage colors' } });
    fireEvent.change(screen.getByLabelText(/Description/i), { target: { value: 'Retro look' } });
    fireEvent.change(screen.getByLabelText(/Group/i), { target: { value: 'Artistic' } });

    expect(saveBtn).not.toBeDisabled();
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(client.createAIEffect).toHaveBeenCalledWith({
        id: 'custom_retro',
        title: 'Retro Style',
        description: 'Retro look',
        display_group: 'Artistic',
        positive_prompt: 'vintage colors',
        negative_prompt: '',
        custom_prompt_placeholder: null,
        enabled: true,
      });
    });
  });

  it('handles editing an AI effect', async () => {
    vi.mocked(client.updateAIEffect).mockResolvedValue({
      ...mockEffects[1],
      title: 'Comic Style Updated',
    });

    renderPage();

    const editBtn = await screen.findByRole('button', { name: 'Edit Comic Illustration' });
    fireEvent.click(editBtn);

    const titleInput = screen.getByLabelText(/Title/i);
    fireEvent.change(titleInput, { target: { value: 'Comic Style Updated' } });

    const saveBtn = screen.getByRole('button', { name: /Save/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(client.updateAIEffect).toHaveBeenCalledWith('illustration_comic', expect.objectContaining({
        title: 'Comic Style Updated',
      }));
    });
  });

  it('triggers duplication with modal confirmation', async () => {
    vi.mocked(client.duplicateAIEffect).mockResolvedValue({
      ...mockEffects[1],
      id: 'illustration_comic_copy',
      title: 'Comic Illustration (Copy)',
    });

    renderPage();

    const menuBtn = await screen.findByRole('button', { name: 'More actions for Comic Illustration' });
    fireEvent.click(menuBtn);

    const dupBtn = screen.getByRole('button', { name: 'Duplicate Comic Illustration' });
    fireEvent.click(dupBtn);

    // Verify modal is open
    expect(screen.getByText('Duplicate AI Effect')).toBeInTheDocument();
    expect(screen.getByText('Are you sure you want to duplicate "Comic Illustration"?')).toBeInTheDocument();

    const confirmBtn = screen.getByRole('button', { name: 'Duplicate' });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(client.duplicateAIEffect).toHaveBeenCalledWith('illustration_comic');
    });
  });

  it('triggers reset with modal warning for built-in effects', async () => {
    vi.mocked(client.resetAIEffect).mockResolvedValue(mockEffects[0]);

    renderPage();

    const menuBtn = await screen.findByRole('button', { name: 'More actions for Portrait Classic' });
    fireEvent.click(menuBtn);

    const resetBtn = screen.getByRole('button', { name: 'Reset Portrait Classic' });
    fireEvent.click(resetBtn);

    // Verify Warning Modal
    expect(screen.getByText('Reset AI Effect')).toBeInTheDocument();

    const confirmBtn = screen.getByRole('button', { name: 'Reset' });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(client.resetAIEffect).toHaveBeenCalledWith('portrait_classic');
    });
  });

  it('triggers delete/disable with modal warning and cancels it', async () => {
    renderPage();

    const menuBtn = await screen.findByRole('button', { name: 'More actions for Comic Illustration' });
    fireEvent.click(menuBtn);

    const deleteBtn = screen.getByRole('button', { name: 'Delete Comic Illustration' });
    fireEvent.click(deleteBtn);

    // Verify Modal
    expect(screen.getByText('Delete AI Effect')).toBeInTheDocument();

    const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
    fireEvent.click(cancelBtn);

    // Verify delete was not called and modal is closed
    expect(client.deleteAIEffect).not.toHaveBeenCalled();
    expect(screen.queryByText('Delete AI Effect')).not.toBeInTheDocument();
  });
});
```

**Step 2: Run the frontend test suite to ensure tests pass**
Run: `cd frontend && npm test -- --run`
Expected: 100% pass for all test suites.

**Step 3: Commit**
```bash
git add frontend/src/__tests__/AIEffects.test.tsx
git commit -m "test: add unit tests for AIEffects page CRUD operations and modals"
```

---

### Task 7: Add SAST (Bandit) to CI

**Status:** Done

**Files:**
- Modify: `/backend/pyproject.toml`
- Modify: `/.github/workflows/ci.yml`

**Step 1: Add bandit to lint dependencies**
Modify `backend/pyproject.toml` under `[project.optional-dependencies]` lint array to add `"bandit>=1.7.0",`:
```toml
lint = [
    "ruff>=0.8.0",
    "bandit>=1.7.0",
]
```

**Step 2: Update CI action steps**
In `.github/workflows/ci.yml` under `backend-tests` job, insert the Bandit execution block right after `Lint with Ruff`:
```yaml
      - name: Security scan with Bandit (SAST)
        run: |
          cd backend
          bandit -r app/ -x tests/
```

**Step 3: Test running bandit locally**
Run: `cd backend && pip install -e ".[lint]" && bandit -r app/ -x tests/`
Expected: Runs successfully, showing no critical issues (or reporting scanning results).

**Step 4: Commit**
```bash
git add backend/pyproject.toml .github/workflows/ci.yml
git commit -m "ci: add bandit SAST to backend dependency and github actions lint stage"
```
