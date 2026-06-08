import { act, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, afterEach } from 'vitest';
import App from '../App';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    getHealth: () => Promise.resolve({ status: 'ok', version: '0.1.0', auth_enabled: false }),
    getDetailedHealth: () => Promise.resolve({
      status: 'ok',
      checks: {
        scheduler: { status: 'ok', age_seconds: 12 },
        database: { status: 'ok' },
        immich: { status: 'not_configured' },
      },
    }),
    getSettings: () => Promise.resolve({}),
    getGenerationHistory: () => Promise.resolve({ items: [], total: 0, latest_event_id: 0 }),
    getFilterPresets: () => Promise.resolve([]),
    getEffectPresets: () => Promise.resolve([]),
    getNotificationPresets: () => Promise.resolve([]),
    getSchedules: () => Promise.resolve([]),
    getImmichFilterOptions: () => Promise.resolve({ albums: [], people: [] }),
    getGenerationModules: () => Promise.resolve([]),
    getGenerationExamples: () => Promise.resolve([]),
  };
});

vi.mock('../api/generationStream', () => ({
  openGenerationStream: () => ({ close: () => {} }),
}));

afterEach(() => {
  window.history.pushState({}, '', '/');
});

function renderApp(path = '/') {
  window.history.pushState({}, '', path);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe('App', () => {
  it('renders without crashing', () => {
    renderApp();
    expect(document.body).toBeTruthy();
  });

  it('shows DailyFX for immich title after loading', async () => {
    renderApp();
    expect(await screen.findAllByText('DailyFX for immich')).toHaveLength(2);
  });

  it('redirects from / to history', async () => {
    renderApp('/');

    expect(await screen.findByText('There are no generations stored in the history database yet.')).toBeInTheDocument();
    expect(document.querySelector('a[href="/history"]')).toHaveAttribute('aria-current', 'page');
    expect(window.location.pathname).toBe('/history');
  });

  it('changes route and active nav state when clicking navigation links', async () => {
    const { container } = renderApp('/history');

    await act(async () => {
      fireEvent.click(container.querySelector('a[href="/schedules"]')!);
    });

    expect(await screen.findByRole('heading', { name: 'Schedules' })).toBeInTheDocument();
    expect(container.querySelector('a[href="/schedules"]')).toHaveAttribute('aria-current', 'page');
    expect(window.location.pathname).toBe('/schedules');
  });

  it('keeps the presets subpage when loaded directly', async () => {
    const { container } = renderApp('/presets/effects');

    expect(await screen.findByText('No effect presets yet')).toBeInTheDocument();
    expect(container.querySelector('a[href="/presets"]')).toHaveAttribute('aria-current', 'page');
    expect(window.location.pathname).toBe('/presets/effects');
  });

  it('supports direct history detail routes', async () => {
    renderApp('/history/man-1');

    expect(await screen.findByText('No items found')).toBeInTheDocument();
    expect(window.location.pathname).toBe('/history/man-1');
  });

  it('supports direct schedule creation routes', async () => {
    renderApp('/schedules/new');

    expect(await screen.findByRole('button', { name: 'Save' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/schedules/new');
  });

  it('shows a 404 page for unknown routes', async () => {
    renderApp('/not-a-real-route');

    expect(await screen.findByText('Page not found')).toBeInTheDocument();
    expect(window.location.pathname).toBe('/not-a-real-route');
  });
});
