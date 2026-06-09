import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  FilterPresetsPage,
  EffectPresetsPage,
  NotificationPresetsPage,
} from '../pages/Presets';
import { AIEffectsPage } from '../pages/AIEffects';
import * as client from '../api/client';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    getFilterPresets: vi.fn(),
    createFilterPreset: vi.fn(),
    updateFilterPreset: vi.fn(),
    deleteFilterPreset: vi.fn(),
    getImmichFilterOptions: vi.fn(),
    getEffectPresets: vi.fn(),
    createEffectPreset: vi.fn(),
    updateEffectPreset: vi.fn(),
    deleteEffectPreset: vi.fn(),
    getGenerationModules: vi.fn(),
    getGenerationExamples: vi.fn(),
    getNotificationPresets: vi.fn(),
    createNotificationPreset: vi.fn(),
    updateNotificationPreset: vi.fn(),
    deleteNotificationPreset: vi.fn(),
    testNotificationPreset: vi.fn(),
    getVapidPublicKey: vi.fn(),
    subscribeWebPush: vi.fn(),
    unsubscribeWebPush: vi.fn(),
    getPushSubscriptions: vi.fn(),
    deletePushSubscription: vi.fn(),
    getAIEffects: vi.fn(),
    createAIEffect: vi.fn(),
    updateAIEffect: vi.fn(),
    duplicateAIEffect: vi.fn(),
    resetAIEffect: vi.fn(),
    deleteAIEffect: vi.fn(),
    exportAIEffects: vi.fn(),
    importAIEffects: vi.fn(),
  };
});

function renderPage(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe('Presets pages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows the filter presets empty state', async () => {
    vi.mocked(client.getFilterPresets).mockResolvedValue([]);
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue({
      albums: [],
      people: [],
    });

    renderPage(<FilterPresetsPage />);

    expect(
      await screen.findByText('No filter presets yet'),
    ).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'New preset' })).toHaveLength(
      2,
    );
  });

  it('shows filter preset validation when creating a new preset', async () => {
    vi.mocked(client.getFilterPresets).mockResolvedValue([]);
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue({
      albums: [],
      people: [],
    });

    renderPage(<FilterPresetsPage />);

    expect(
      await screen.findByText('No filter presets yet'),
    ).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: 'New preset' })[0]);

    expect(screen.getByText('New filter preset')).toBeInTheDocument();
    expect(screen.getByText('Preset name is required.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Save/ })).toBeDisabled();
  });

  it('shows the effect presets empty state', async () => {
    vi.mocked(client.getEffectPresets).mockResolvedValue([]);
    vi.mocked(client.getGenerationModules).mockResolvedValue([]);
    vi.mocked(client.getGenerationExamples).mockResolvedValue([]);

    renderPage(<EffectPresetsPage />);

    expect(
      await screen.findByText('No effect presets yet'),
    ).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'New preset' })).toHaveLength(
      2,
    );
  });

  it('shows notification preset validation when creating a new preset', async () => {
    vi.mocked(client.getNotificationPresets).mockResolvedValue([]);
    vi.mocked(client.getPushSubscriptions).mockResolvedValue({
      count: 0,
      subscriptions: [],
    });

    renderPage(<NotificationPresetsPage />);

    expect(
      await screen.findByText('No notification presets yet'),
    ).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: 'New preset' })[0]);

    expect(screen.getByText('New notification preset')).toBeInTheDocument();
    expect(screen.getByText('Preset name is required.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Save/ })).toBeDisabled();
  });

  it('keeps secondary AI effect actions behind a compact action menu', async () => {
    vi.mocked(client.getAIEffects).mockResolvedValue([
      {
        id: 'ai_caricature',
        title: 'AI Caricature',
        description: 'Turns a portrait into a caricature.',
        display_group: 'Portrait',
        positive_prompt: 'Make a caricature.',
        negative_prompt: '',
        custom_prompt_placeholder: null,
        enabled: true,
        hidden: false,
        source: 'builtin',
        builtin_hash: 'abc',
        latest_builtin_hash: 'abc',
        user_modified_at: null,
        created_at: '2026-05-30T04:00:00.000Z',
        updated_at: '2026-05-30T04:00:00.000Z',
      },
    ]);

    renderPage(<AIEffectsPage />);

    expect(await screen.findByText('AI Caricature')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Edit AI Caricature' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Duplicate AI Caricature' }),
    ).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', { name: 'More actions for AI Caricature' }),
    );

    expect(
      screen.getByRole('button', { name: 'Duplicate AI Caricature' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Reset AI Caricature' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Delete AI Caricature' }),
    ).toBeInTheDocument();
  });
});
