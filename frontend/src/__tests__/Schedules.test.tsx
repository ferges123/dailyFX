import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { SchedulesPage } from '../pages/Schedules';
import * as client from '../api/client';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    getSchedules: vi.fn(),
    getFilterPresets: vi.fn(),
    getEffectPresets: vi.fn(),
    getNotificationPresets: vi.fn(),
    createSchedule: vi.fn(),
    updateSchedule: vi.fn(),
    deleteSchedule: vi.fn(),
    triggerScheduleNow: vi.fn(),
  };
});

function renderSchedules() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/schedules" element={<SchedulesPage />} />
          <Route path="/schedules/new" element={<SchedulesPage />} />
          <Route
            path="/schedules/:scheduleId/edit"
            element={<SchedulesPage />}
          />
          <Route path="*" element={<SchedulesPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>,
  );
}

describe('SchedulesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows an empty state when no schedules exist', async () => {
    vi.mocked(client.getSchedules).mockResolvedValue([]);
    vi.mocked(client.getFilterPresets).mockResolvedValue([]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([]);

    renderSchedules();

    expect(await screen.findByText('No schedules yet')).toBeInTheDocument();
    expect(
      screen.getAllByRole('button', { name: 'New schedule' }),
    ).toHaveLength(2);
  });

  it('renders schedule status and run metadata', async () => {
    vi.mocked(client.getSchedules).mockResolvedValue([
      {
        id: 1,
        name: 'Morning run',
        enabled: true,
        schedule_expr: 'daily@08:00',
        filter_preset_id: 2,
        effect_preset_id: 3,
        notification_preset_ids: [4],
        album_name: 'AI Photos',
        ai_vision_provider: 'local',
        ai_vision_model: 'qwen2.5-vl',
        ai_image_provider: 'local',
        ai_image_model: 'flux.1',
        ai_prompt_enrichment: true,
        ai_photo_selection_enabled: true,
        last_run_at: '2026-05-30T05:00:00.000Z',
        next_run_at: '2026-05-31T08:00:00.000Z',
        last_tick_status: 'error',
        last_tick_reason: 'timeout',
        last_task_id: 'task-1',
        created_at: '2026-05-30T04:00:00.000Z',
        filter_preset_name: 'Default filter',
        effect_preset_name: 'Default effect',
        notification_preset_names: ['Phone'],
      },
    ]);
    vi.mocked(client.getFilterPresets).mockResolvedValue([
      {
        id: 2,
        name: 'Default filter',
        album_ids: [],
        person_filters: [],
        start_date: null,
        end_date: null,
        media_type: 'photo',
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([
      {
        id: 3,
        name: 'Default effect',
        groups: {},
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([
      {
        id: 4,
        name: 'Phone',
        provider: 'web',
        url: null,
        topic: null,
        has_token: false,
        token_masked: null,
        webhook_url: null,
        created_at: '2026-05-30T04:00:00.000Z',
        push_subscription_ids: [],
      },
    ]);

    renderSchedules();

    expect(await screen.findAllByText('Morning run')).toHaveLength(2);
    expect(screen.getAllByText('Next run').length).toBeGreaterThan(0);
    expect(
      screen.getAllByRole('button', { name: 'Run now' }).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText('error · timeout').length).toBeGreaterThan(0);
    expect(screen.getByText('Vision: local (qwen2.5-vl)')).toBeInTheDocument();
    expect(screen.getByText('Image: local (flux.1)')).toBeInTheDocument();
    expect(screen.getAllByText('AI photo selection on').length).toBeGreaterThan(0);
  });

  it('uses a two-column schedule list', async () => {
    vi.mocked(client.getSchedules).mockResolvedValue([
      {
        id: 1,
        name: 'Morning run',
        enabled: true,
        schedule_expr: 'daily@08:00',
        filter_preset_id: 2,
        effect_preset_id: 3,
        notification_preset_ids: [4],
        album_name: 'AI Photos',
        ai_vision_provider: 'local',
        ai_vision_model: 'qwen2.5-vl',
        ai_image_provider: 'local',
        ai_image_model: 'flux.1',
        ai_prompt_enrichment: true,
        ai_photo_selection_enabled: false,
        last_run_at: null,
        next_run_at: null,
        last_tick_status: null,
        last_tick_reason: null,
        last_task_id: null,
        created_at: '2026-06-10T04:00:00.000Z',
        filter_preset_name: 'Default filter',
        effect_preset_name: 'Default effect',
        notification_preset_names: ['Phone'],
      },
    ]);
    vi.mocked(client.getFilterPresets).mockResolvedValue([]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([]);

    renderSchedules();

    expect(await screen.findByText('Morning run')).toBeInTheDocument();
    expect(screen.getByLabelText('Schedules list')).toHaveClass(
      'lg:grid-cols-2',
    );
  });

  it('opens the create form when loaded on the new schedule route', async () => {
    window.history.pushState({}, '', '/schedules/new');
    vi.mocked(client.getSchedules).mockResolvedValue([]);
    vi.mocked(client.getFilterPresets).mockResolvedValue([]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([]);

    renderSchedules();

    expect(
      await screen.findByRole('button', { name: 'Save' }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe('/schedules/new');
  });

  it('opens the edit form when an existing schedule is edited', async () => {
    window.history.pushState({}, '', '/schedules');
    vi.mocked(client.getSchedules).mockResolvedValue([
      {
        id: 1,
        name: 'Morning run',
        enabled: true,
        schedule_expr: 'daily@08:00',
        filter_preset_id: 2,
        effect_preset_id: 3,
        notification_preset_ids: [4],
        album_name: 'AI Photos',
        ai_vision_provider: 'local',
        ai_vision_model: 'qwen2.5-vl',
        ai_image_provider: 'local',
        ai_image_model: 'flux.1',
        ai_prompt_enrichment: true,
        ai_photo_selection_enabled: false,
        last_run_at: null,
        next_run_at: null,
        last_tick_status: null,
        last_tick_reason: null,
        last_task_id: null,
        created_at: '2026-05-30T04:00:00.000Z',
        filter_preset_name: 'Default filter',
        effect_preset_name: 'Default effect',
        notification_preset_names: ['Phone'],
      },
    ]);
    vi.mocked(client.getFilterPresets).mockResolvedValue([
      {
        id: 2,
        name: 'Default filter',
        album_ids: [],
        person_filters: [],
        start_date: null,
        end_date: null,
        media_type: 'photo',
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([
      {
        id: 3,
        name: 'Default effect',
        groups: {},
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([
      {
        id: 4,
        name: 'Phone',
        provider: 'web',
        url: null,
        topic: null,
        has_token: false,
        token_masked: null,
        webhook_url: null,
        created_at: '2026-05-30T04:00:00.000Z',
        push_subscription_ids: [],
      },
    ]);

    renderSchedules();

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }));

    const formPanel = await screen.findByLabelText('Schedule form panel');
    expect(
      within(formPanel).getByText('Editing: Morning run'),
    ).toBeInTheDocument();
    expect(
      within(formPanel).getByDisplayValue('Morning run'),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe('/schedules/1/edit');

    fireEvent.click(within(formPanel).getByRole('button', { name: 'Cancel' }));

    await waitFor(() => expect(window.location.pathname).toBe('/schedules'));
    expect(
      screen.queryByLabelText('Schedule form panel'),
    ).not.toBeInTheDocument();
  });

  it('uses a dedicated editing surface instead of keeping the schedule browser visible', async () => {
    window.history.pushState({}, '', '/schedules');
    vi.mocked(client.getSchedules).mockResolvedValue([
      {
        id: 1,
        name: 'Morning run',
        enabled: true,
        schedule_expr: 'daily@08:00',
        filter_preset_id: 2,
        effect_preset_id: 3,
        notification_preset_ids: [4],
        album_name: 'AI Photos',
        ai_vision_provider: 'local',
        ai_vision_model: 'qwen2.5-vl',
        ai_image_provider: 'local',
        ai_image_model: 'flux.1',
        ai_prompt_enrichment: true,
        ai_photo_selection_enabled: false,
        last_run_at: null,
        next_run_at: null,
        last_tick_status: null,
        last_tick_reason: null,
        last_task_id: null,
        created_at: '2026-05-30T04:00:00.000Z',
        filter_preset_name: 'Default filter',
        effect_preset_name: 'Default effect',
        notification_preset_names: ['Phone'],
      },
    ]);
    vi.mocked(client.getFilterPresets).mockResolvedValue([
      {
        id: 2,
        name: 'Default filter',
        album_ids: [],
        person_filters: [],
        start_date: null,
        end_date: null,
        media_type: 'photo',
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([
      {
        id: 3,
        name: 'Default effect',
        groups: {},
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([
      {
        id: 4,
        name: 'Phone',
        provider: 'web',
        url: null,
        topic: null,
        has_token: false,
        token_masked: null,
        webhook_url: null,
        created_at: '2026-05-30T04:00:00.000Z',
        push_subscription_ids: [],
      },
    ]);

    renderSchedules();

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }));

    const formPanel = await screen.findByLabelText('Schedule form panel');
    expect(
      within(formPanel).getByText('Editing: Morning run'),
    ).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText('Search schedules...'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Run now' }),
    ).not.toBeInTheDocument();
  });

  it('normalizes unsupported Xiaomi vision models when loading an edit form', async () => {
    window.history.pushState({}, '', '/schedules');
    vi.mocked(client.getSchedules).mockResolvedValue([
      {
        id: 1,
        name: 'Morning run',
        enabled: true,
        schedule_expr: 'daily@08:00',
        filter_preset_id: 2,
        effect_preset_id: 3,
        notification_preset_ids: [4],
        album_name: 'AI Photos',
        ai_vision_provider: 'xiaomi',
        ai_vision_model: 'mimo-v2.5-pro',
        ai_image_provider: 'local',
        ai_image_model: 'flux.1',
        ai_prompt_enrichment: true,
        ai_photo_selection_enabled: false,
        last_run_at: null,
        next_run_at: null,
        last_tick_status: null,
        last_tick_reason: null,
        last_task_id: null,
        created_at: '2026-05-30T04:00:00.000Z',
        filter_preset_name: 'Default filter',
        effect_preset_name: 'Default effect',
        notification_preset_names: ['Phone'],
      },
    ]);
    vi.mocked(client.getFilterPresets).mockResolvedValue([
      {
        id: 2,
        name: 'Default filter',
        album_ids: [],
        person_filters: [],
        start_date: null,
        end_date: null,
        media_type: 'photo',
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([
      {
        id: 3,
        name: 'Default effect',
        groups: {},
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([
      {
        id: 4,
        name: 'Phone',
        provider: 'web',
        url: null,
        topic: null,
        has_token: false,
        token_masked: null,
        webhook_url: null,
        created_at: '2026-05-30T04:00:00.000Z',
        push_subscription_ids: [],
      },
    ]);

    renderSchedules();

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }));

    const formPanel = await screen.findByLabelText('Schedule form panel');
    expect(
      within(formPanel).getByDisplayValue('mimo-v2.5'),
    ).toBeInTheDocument();
    expect(
      within(formPanel).queryByDisplayValue('mimo-v2.5-pro'),
    ).not.toBeInTheDocument();
  });

  it('saves edits from the right panel form', async () => {
    window.history.pushState({}, '', '/schedules');
    const schedule = {
      id: 1,
      name: 'Morning run',
      enabled: true,
      schedule_expr: 'daily@08:00',
      filter_preset_id: 2,
      effect_preset_id: 3,
      notification_preset_ids: [4],
      album_name: 'AI Photos',
      ai_vision_provider: 'local',
      ai_vision_model: 'qwen2.5-vl',
      ai_image_provider: 'local',
      ai_image_model: 'flux.1',
      ai_prompt_enrichment: true,
      ai_photo_selection_enabled: false,
      last_run_at: null,
      next_run_at: null,
      last_tick_status: null,
      last_tick_reason: null,
      last_task_id: null,
      created_at: '2026-05-30T04:00:00.000Z',
      filter_preset_name: 'Default filter',
      effect_preset_name: 'Default effect',
      notification_preset_names: ['Phone'],
    };
    vi.mocked(client.getSchedules).mockResolvedValue([schedule]);
    vi.mocked(client.getFilterPresets).mockResolvedValue([
      {
        id: 2,
        name: 'Default filter',
        album_ids: [],
        person_filters: [],
        start_date: null,
        end_date: null,
        media_type: 'photo',
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([
      {
        id: 3,
        name: 'Default effect',
        groups: {},
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([
      {
        id: 4,
        name: 'Phone',
        provider: 'web',
        url: null,
        topic: null,
        has_token: false,
        token_masked: null,
        webhook_url: null,
        created_at: '2026-05-30T04:00:00.000Z',
        push_subscription_ids: [],
      },
    ]);
    vi.mocked(client.updateSchedule).mockResolvedValue(schedule);

    renderSchedules();

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }));
    const formPanel = await screen.findByLabelText('Schedule form panel');
    fireEvent.click(within(formPanel).getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(client.updateSchedule).toHaveBeenCalled());
  });

  it('saves AI photo selection with schedule edits', async () => {
    window.history.pushState({}, '', '/schedules');
    const schedule = {
      id: 1,
      name: 'Morning run',
      enabled: true,
      schedule_expr: 'daily@08:00',
      filter_preset_id: 2,
      effect_preset_id: 3,
      notification_preset_ids: [4],
      album_name: 'AI Photos',
      ai_vision_provider: 'local',
      ai_vision_model: 'qwen2.5-vl',
      ai_image_provider: 'local',
      ai_image_model: 'flux.1',
      ai_prompt_enrichment: false,
      ai_photo_selection_enabled: false,
      last_run_at: null,
      next_run_at: null,
      last_tick_status: null,
      last_tick_reason: null,
      last_task_id: null,
      created_at: '2026-05-30T04:00:00.000Z',
      filter_preset_name: 'Default filter',
      effect_preset_name: 'Default effect',
      notification_preset_names: ['Phone'],
    };
    vi.mocked(client.getSchedules).mockResolvedValue([schedule]);
    vi.mocked(client.getFilterPresets).mockResolvedValue([
      {
        id: 2,
        name: 'Default filter',
        album_ids: [],
        person_filters: [],
        start_date: null,
        end_date: null,
        media_type: 'photo',
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([
      {
        id: 3,
        name: 'Default effect',
        groups: {},
        created_at: '2026-05-30T04:00:00.000Z',
      },
    ]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([
      {
        id: 4,
        name: 'Phone',
        provider: 'web',
        url: null,
        topic: null,
        has_token: false,
        token_masked: null,
        webhook_url: null,
        created_at: '2026-05-30T04:00:00.000Z',
        push_subscription_ids: [],
      },
    ]);
    vi.mocked(client.updateSchedule).mockResolvedValue({
      ...schedule,
      ai_photo_selection_enabled: true,
    });

    renderSchedules();

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }));
    const formPanel = await screen.findByLabelText('Schedule form panel');
    fireEvent.click(within(formPanel).getByLabelText('AI photo selection'));
    fireEvent.click(within(formPanel).getByRole('button', { name: 'Save' }));

    await waitFor(() =>
      expect(client.updateSchedule).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ ai_photo_selection_enabled: true }),
      ),
    );
  });

  it('disables AI photo selection when no vision provider is selected', async () => {
    window.history.pushState({}, '', '/schedules/new');
    vi.mocked(client.getSchedules).mockResolvedValue([]);
    vi.mocked(client.getFilterPresets).mockResolvedValue([]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([]);

    renderSchedules();

    const formPanel = await screen.findByLabelText('Schedule form panel');

    expect(within(formPanel).getByLabelText('AI photo selection')).toBeDisabled();
  });
});
