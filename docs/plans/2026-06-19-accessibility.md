# Accessibility (A11y) Improvements Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Improve web accessibility (A11y) inside modals, form controls, and dynamic alert messages across the frontend application.

**Architecture:** We will apply standard WAI-ARIA roles, attributes (`role="dialog"`, `aria-modal="true"`, `aria-labelledby`, `aria-label`, `aria-live="polite"`), and verify their existence using React Testing Library in a dedicated test suite.

**Tech Stack:** TypeScript, React, Vitest, React Testing Library.

---

### Task 1: Create A11y Unit Tests

**Files:**
- Create: `frontend/src/__tests__/Accessibility.test.tsx`

**Step 1: Write the test suite**
Create unit tests to verify the accessibility attributes for ConfirmModal, ConfirmDeleteModal, UploadModal, LightboxModal, HistoryPage controls, and Settings dynamic status message.

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ConfirmModal } from '../components/ConfirmModal';
import { ConfirmDeleteModal } from '../pages/History/ConfirmDeleteModal';
import { UploadModal } from '../pages/History/UploadModal';
import { LightboxModal } from '../pages/History/LightboxModal';
import { HistoryPage } from '../pages/History/HistoryPage';
import { SettingsPage } from '../pages/Settings';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

vi.mock('../api/client', () => ({
  getSettings: vi.fn(() => Promise.resolve({
    immich_url: 'http://localhost',
    local_ai_base_url: 'http://localhost',
    ai_vision_hourly_limit: 10,
    ai_image_hourly_limit: 10,
  })),
  getGenerationHistory: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
  getImmichFilterOptions: vi.fn(() => Promise.resolve([])),
  getImmichAssetExif: vi.fn(() => Promise.resolve({})),
  getImmichAssetDetailUrl: vi.fn(() => 'http://localhost'),
}));

vi.mock('../api/generationStream', () => ({
  openGenerationStream: vi.fn(() => ({ close: vi.fn() })),
}));

describe('Accessibility Attributes', () => {
  it('ConfirmModal has dialog role, aria-modal, aria-labelledby, and close button label', () => {
    const { container } = render(
      <ConfirmModal
        isOpen={true}
        title="Test Title"
        description="Test Desc"
        onConfirm={() => {}}
        onClose={() => {}}
      />
    );
    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'confirm-modal-title');
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });

  it('ConfirmDeleteModal has dialog role, aria-modal, aria-labelledby, and close button label', () => {
    const { container } = render(
      <ConfirmDeleteModal
        isOpen={true}
        onClose={() => {}}
        onConfirm={() => {}}
        variant="all"
        isPending={false}
      />
    );
    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'delete-modal-title');
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });

  it('UploadModal has dialog role, aria-modal, aria-labelledby, and close button label', () => {
    const mockEntry = {
      id: 1,
      task_id: 'task-1',
      generation_type: 'instafilter',
      status: 'PENDING_REVIEW',
      title: 'Title',
      summary: 'Summary',
      source_asset_ids: '["asset-1"]',
      output_path: 'path',
      image_url: 'url',
      provider: 'local',
      model: 'pilgram',
      output_format: 'png',
      aspect_ratio: '1:1',
      prompt: 'prompt',
      config_json: '{}',
      created_at: '2026-06-19T00:00:00Z',
    };
    const { container } = render(
      <UploadModal
        isOpen={true}
        onClose={() => {}}
        entry={mockEntry}
        albums={[]}
        onConfirm={() => {}}
        isPending={false}
      />
    );
    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'upload-modal-title');
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });

  it('LightboxModal has dialog role, aria-modal, aria-labelledby, and close button label', () => {
    const mockEntry = {
      id: 1,
      task_id: 'task-1',
      generation_type: 'instafilter',
      status: 'PENDING_REVIEW',
      title: 'Title',
      summary: 'Summary',
      source_asset_ids: '["asset-1"]',
      output_path: 'path',
      image_url: 'url',
      provider: 'local',
      model: 'pilgram',
      output_format: 'png',
      aspect_ratio: '1:1',
      prompt: 'prompt',
      config_json: '{}',
      created_at: '2026-06-19T00:00:00Z',
    };
    const { container } = render(
      <LightboxModal
        isOpen={true}
        onClose={() => {}}
        imageUrl="url"
        entry={mockEntry}
        exif={null}
      />
    );
    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'lightbox-modal-title');
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });

  it('HistoryPage form fields have aria-labels', async () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <HistoryPage />
        </BrowserRouter>
      </QueryClientProvider>
    );
    expect(await screen.findByRole('textbox', { name: 'Search history' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Filter history by status' })).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**
Run: `npm test src/__tests__/Accessibility.test.tsx`
Expected: FAIL due to missing files/attributes.

---

### Task 2: Implement Modal Accessibility Attributes

**Files:**
- Modify: `frontend/src/components/ConfirmModal.tsx`
- Modify: `frontend/src/pages/History/ConfirmDeleteModal.tsx`
- Modify: `frontend/src/pages/History/UploadModal.tsx`
- Modify: `frontend/src/pages/History/LightboxModal.tsx`

**Step 1: Apply accessibility attributes**
Update the components with dialog roles, modal flags, labeledby tags, and close button aria-labels.

**Step 2: Run test to verify passes**
Run: `npm test src/__tests__/Accessibility.test.tsx`
Expected: PASS (except for HistoryPage tests if those are not yet modified).

---

### Task 3: Implement HistoryPage Controls Accessibility

**Files:**
- Modify: `frontend/src/pages/History/HistoryPage.tsx`

**Step 1: Add aria-labels to input and select controls**
Add `aria-label="Search history"` and `aria-label="Filter history by status"`.

**Step 2: Run test to verify passes**
Run: `npm test src/__tests__/Accessibility.test.tsx`
Expected: PASS.

---

### Task 4: Implement Settings Saved Message Live Announcement

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`
- Test: Add a test checking `aria-live` container in `frontend/src/__tests__/Accessibility.test.tsx`

**Step 1: Wrap save message in a container with aria-live="polite"**

**Step 2: Run test to verify passes**
Run: `npm test src/__tests__/Accessibility.test.tsx`
Expected: PASS.

---

### Task 5: Verify Entire Suite & Build

**Step 1: Run all tests**
Run: `npm test`
Expected: PASS.

**Step 2: Run linter, formatting, and build**
Run: `npm run build && npm run lint && npm run format`
Expected: PASS.
