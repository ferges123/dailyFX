import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
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
        <SchedulesPage />
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
    expect(screen.getAllByRole('button', { name: 'New schedule' })).toHaveLength(3);
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
    vi.mocked(client.getFilterPresets).mockResolvedValue([{ id: 2, name: 'Default filter', album_ids: [], person_filters: [], start_date: null, end_date: null, media_type: 'photo', created_at: '2026-05-30T04:00:00.000Z' }]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([{ id: 3, name: 'Default effect', groups: {}, created_at: '2026-05-30T04:00:00.000Z' }]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([{ id: 4, name: 'Phone', provider: 'web', url: null, topic: null, has_token: false, token_masked: null, webhook_url: null, created_at: '2026-05-30T04:00:00.000Z' }]);

    renderSchedules();

    expect(await screen.findAllByText('Morning run')).toHaveLength(3);
    expect(screen.getAllByText('Next run').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Last run').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Last result').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: 'Run now' }).length).toBeGreaterThan(0);
    expect(screen.getAllByText('error · timeout').length).toBeGreaterThan(0);
    expect(screen.getByText('Vision model')).toBeInTheDocument();
    expect(screen.getByText('Vision: local (qwen2.5-vl)')).toBeInTheDocument();
    expect(screen.getByText('Image: local (flux.1)')).toBeInTheDocument();
  });

  it('opens the create form when loaded on the new schedule route', async () => {
    window.history.pushState({}, '', '/schedules/new');
    vi.mocked(client.getSchedules).mockResolvedValue([]);
    vi.mocked(client.getFilterPresets).mockResolvedValue([]);
    vi.mocked(client.getEffectPresets).mockResolvedValue([]);
    vi.mocked(client.getNotificationPresets).mockResolvedValue([]);

    renderSchedules();

    expect(await screen.findByRole('button', { name: 'Save' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/schedules/new');
  });
});
