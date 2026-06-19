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
import { type GenerationHistoryEntry } from '../api/client';

vi.mock('../api/client', () => ({
  getSettings: vi.fn(() =>
    Promise.resolve({
      immich_url: 'http://localhost',
      local_ai_base_url: 'http://localhost',
      ai_vision_hourly_limit: 10,
      ai_image_hourly_limit: 10,
      app_access_token: null,
    }),
  ),
  getGenerationHistory: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
  getImmichFilterOptions: vi.fn(() => Promise.resolve([])),
  getImmichAssetExif: vi.fn(() => Promise.resolve({})),
  acceptGeneration: vi.fn(() => Promise.resolve({})),
  rejectGeneration: vi.fn(() => Promise.resolve({})),
  retryGenerationAcceptance: vi.fn(() => Promise.resolve({})),
  clearRejectedCache: vi.fn(() => Promise.resolve({})),
  clearGenerationCache: vi.fn(() => Promise.resolve({})),
  getImmichAssetDetailUrl: vi.fn(() => 'http://localhost'),
  getHealth: vi.fn(() =>
    Promise.resolve({ status: 'ok', version: '0.3.24', auth_enabled: false }),
  ),
  getDetailedHealth: vi.fn(() => Promise.resolve({ status: 'ok', checks: {} })),
  clearHistoryByStatus: vi.fn(() => Promise.resolve({})),
  updateSettings: vi.fn(() => Promise.resolve({})),
  testImmichConnection: vi.fn(() => Promise.resolve({})),
  testOpenAIConnection: vi.fn(() => Promise.resolve({})),
  testGeminiConnection: vi.fn(() => Promise.resolve({})),
  testOpenRouterConnection: vi.fn(() => Promise.resolve({})),
  testBytePlusConnection: vi.fn(() => Promise.resolve({})),
  testLocalAIConnection: vi.fn(() => Promise.resolve({})),
  testXiaomiConnection: vi.fn(() => Promise.resolve({})),
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
      />,
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
      />,
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
        entry={mockEntry as unknown as GenerationHistoryEntry}
        albums={[]}
        onConfirm={() => {}}
        isPending={false}
      />,
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
        entry={mockEntry as unknown as GenerationHistoryEntry}
        exif={null}
      />,
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
      </QueryClientProvider>,
    );
    expect(
      await screen.findByRole('textbox', { name: 'Search history' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('combobox', { name: 'Filter history by status' }),
    ).toBeInTheDocument();
  });

  it('SettingsPage has an aria-live region for dynamic alerts', async () => {
    const queryClient = new QueryClient();
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <SettingsPage />
      </QueryClientProvider>,
    );
    const { waitFor } = await import('@testing-library/react');
    await waitFor(() => {
      const saveStatus = container.querySelector(
        '[data-testid="save-status-container"]',
      );
      expect(saveStatus).toBeInTheDocument();
      expect(saveStatus).toHaveAttribute('aria-live', 'polite');
    });
  });
});
