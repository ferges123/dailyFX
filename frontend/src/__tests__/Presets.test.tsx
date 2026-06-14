import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

  it('uses a two-column list and scrolls to the filter preset edit form', async () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    vi.mocked(client.getFilterPresets).mockResolvedValue([
      {
        id: 1,
        name: 'Trip filters',
        album_ids: ['album-1'],
        person_filters: [],
        start_date: null,
        end_date: null,
        media_type: 'photo',
        created_at: '2026-06-10T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue({
      albums: [
        {
          id: 'album-1',
          album_name: 'Travel',
          asset_count: 12,
          thumbnail_asset_id: null,
        },
      ],
      people: [],
    });

    renderPage(<FilterPresetsPage />);

    expect(await screen.findByText('Trip filters')).toBeInTheDocument();
    expect(screen.getByLabelText('Filter presets list')).toHaveClass(
      'lg:grid-cols-2',
    );

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }));

    expect(await screen.findByText('Editing: Trip filters')).toBeInTheDocument();
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalled());
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

  it('uses a two-column list for effect presets', async () => {
    vi.mocked(client.getEffectPresets).mockResolvedValue([
      {
        id: 1,
        name: 'Daily effects',
        groups: {},
        created_at: '2026-06-10T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getGenerationModules).mockResolvedValue([]);
    vi.mocked(client.getGenerationExamples).mockResolvedValue([]);

    renderPage(<EffectPresetsPage />);

    expect(await screen.findByText('Daily effects')).toBeInTheDocument();
    expect(screen.getByLabelText('Effect presets list')).toHaveClass(
      'lg:grid-cols-2',
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

  it('keeps notification presets on the shared two-column list', async () => {
    vi.mocked(client.getNotificationPresets).mockResolvedValue([
      {
        id: 1,
        name: 'Phone',
        provider: 'web',
        url: null,
        topic: null,
        has_token: false,
        token_masked: null,
        webhook_url: null,
        created_at: '2026-06-10T04:00:00.000Z',
        push_subscription_ids: [],
      },
    ]);
    vi.mocked(client.getPushSubscriptions).mockResolvedValue({
      count: 0,
      subscriptions: [],
    });

    renderPage(<NotificationPresetsPage />);

    expect(await screen.findByText('Phone')).toBeInTheDocument();
    expect(screen.getByLabelText('Notification presets list')).toHaveClass(
      'lg:grid-cols-2',
    );
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

  it('uses a two-column list and scrolls to the AI effect edit form', async () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
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
    expect(screen.getByLabelText('AI effects list: Portrait')).toHaveClass(
      'lg:grid-cols-2',
    );

    fireEvent.click(
      screen.getByRole('button', { name: 'Edit AI Caricature' }),
    );

    expect(await screen.findByText('Editing: AI Caricature')).toBeInTheDocument();
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalled());
  });

  it('matches preset tab header controls for AI effects', async () => {
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
      {
        id: 'ai_anime',
        title: 'AI Anime',
        description: 'Anime style.',
        display_group: 'Illustration',
        positive_prompt: 'Make anime.',
        negative_prompt: '',
        custom_prompt_placeholder: null,
        enabled: true,
        hidden: false,
        source: 'builtin',
        builtin_hash: 'def',
        latest_builtin_hash: 'def',
        user_modified_at: null,
        created_at: '2026-05-30T04:00:00.000Z',
        updated_at: '2026-05-30T04:00:00.000Z',
      },
      {
        id: 'ai_comic',
        title: 'AI Comic',
        description: 'Comic style.',
        display_group: 'Illustration',
        positive_prompt: 'Make comic.',
        negative_prompt: '',
        custom_prompt_placeholder: null,
        enabled: true,
        hidden: false,
        source: 'builtin',
        builtin_hash: 'ghi',
        latest_builtin_hash: 'ghi',
        user_modified_at: null,
        created_at: '2026-05-30T04:00:00.000Z',
        updated_at: '2026-05-30T04:00:00.000Z',
      },
      {
        id: 'ai_custom',
        title: 'AI Custom',
        description: 'Custom style.',
        display_group: null,
        positive_prompt: 'Make custom.',
        negative_prompt: '',
        custom_prompt_placeholder: null,
        enabled: true,
        hidden: false,
        source: 'custom',
        builtin_hash: null,
        latest_builtin_hash: null,
        user_modified_at: null,
        created_at: '2026-05-30T04:00:00.000Z',
        updated_at: '2026-05-30T04:00:00.000Z',
      },
    ]);

    renderPage(<AIEffectsPage />);

    expect(await screen.findByText('4 preset(s)')).toBeInTheDocument();
    expect(
      screen.queryByText(
        'Built-in seeds are synced from JSON into the database. Runtime edits stay local.',
      ),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Filter by group')).not.toBeInTheDocument();
    expect(screen.getByLabelText('AI effects group filter')).toBeInTheDocument();
    expect(screen.getByLabelText('AI effects header actions')).toHaveClass(
      'sm:flex-row',
    );
  });

  it('displays error message when Web Push subscription fails', async () => {
    // 1. Setup mocks for Web Push support in testing environment
    const originalNotification = (globalThis as any).Notification;
    const originalNavigator = (globalThis as any).navigator;
    const originalSecureContext = (globalThis as any).isSecureContext;
    const originalPushManager = (globalThis as any).PushManager;

    (globalThis as any).isSecureContext = true;
    (globalThis as any).PushManager = {};
    (globalThis as any).Notification = {
      permission: 'granted',
      requestPermission: vi.fn().mockResolvedValue('granted'),
    };

    const mockPushManager = {
      subscribe: vi.fn().mockRejectedValue(new Error('VAPID key error or permission denied')),
      getSubscription: vi.fn().mockResolvedValue(null),
    };
    const mockServiceWorker = {
      ready: Promise.resolve({
        pushManager: mockPushManager,
      }),
    };
    Object.defineProperty(globalThis, 'navigator', {
      value: {
        ...originalNavigator,
        serviceWorker: mockServiceWorker,
      },
      writable: true,
    });

    vi.mocked(client.getNotificationPresets).mockResolvedValue([]);
    vi.mocked(client.getPushSubscriptions).mockResolvedValue({
      count: 0,
      subscriptions: [],
    });
    vi.mocked(client.getVapidPublicKey).mockResolvedValue('mock-vapid-key');

    // 2. Render Page
    renderPage(<NotificationPresetsPage />);

    // 3. Open Form
    expect(
      await screen.findByText('No notification presets yet'),
    ).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: 'New preset' })[0]);

    // 5. Click Subscribe button
    const subscribeButton = await screen.findByText('Subscribe this browser');
    fireEvent.click(subscribeButton);

    // 6. Verify that the error is caught and displayed
    expect(
      await screen.findByText(/Failed to update subscription:/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Permission denied. Please enable notifications for this site/),
    ).toBeInTheDocument();

    // 7. Cleanup global mocks
    (globalThis as any).Notification = originalNotification;
    (globalThis as any).isSecureContext = originalSecureContext;
    (globalThis as any).PushManager = originalPushManager;
    Object.defineProperty(globalThis, 'navigator', {
      value: originalNavigator,
      writable: true,
    });
  });
});
