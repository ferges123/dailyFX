import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, afterEach } from 'vitest';
import App from '../App';
import { APP_VERSION } from '../version';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    getHealth: () =>
      Promise.resolve({ status: 'ok', version: '0.2.14', auth_enabled: false }),
    getDetailedHealth: () =>
      Promise.resolve({
        status: 'ok',
        checks: {
          scheduler: { status: 'ok', age_seconds: 12 },
          database: { status: 'ok' },
          immich: { status: 'not_configured' },
        },
      }),
    getSettings: () => Promise.resolve({}),
    getGenerationHistory: () =>
      Promise.resolve({ items: [], total: 0, latest_event_id: 0 }),
    getFilterPresets: () => Promise.resolve([]),
    getEffectPresets: () => Promise.resolve([]),
    getNotificationPresets: () => Promise.resolve([]),
    getSchedules: () => Promise.resolve([]),
    getImmichFilterOptions: () => Promise.resolve({ albums: [], people: [] }),
    getGenerationModules: () => Promise.resolve([]),
    getStudioModules: () => Promise.resolve([]),
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
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
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
    expect(
      await screen.findAllByText('DailyFX for immich', {}, { timeout: 5000 }),
    ).toHaveLength(2);
  });

  it('uses the light logo for the app chrome brand icon', async () => {
    renderApp();

    expect(
      await screen.findAllByRole('img', { name: 'DailyFX logo' }),
    ).toHaveLength(2);
    expect(screen.getAllByRole('img', { name: 'DailyFX logo' })).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          src: expect.stringContaining('/logo_light.png'),
        }),
      ]),
    );
  });

  it('shows the shared frontend app version in desktop and mobile chrome', async () => {
    renderApp('/settings');

    await waitFor(() => {
      expect(
        screen.getAllByText(new RegExp(`DailyFX ${APP_VERSION}`)),
      ).toHaveLength(2);
    });
  });

  it('shows a route loading fallback while lazy page modules load', async () => {
    renderApp('/schedules');

    expect(await screen.findByText('Loading page...')).toBeInTheDocument();
  });

  it('redirects from / to history', async () => {
    renderApp('/');

    expect(
      await screen.findByText(
        'There are no generations stored in the history database yet.',
        {},
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();
    expect(document.querySelector('a[href="/history"]')).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(window.location.pathname).toBe('/history');
  });

  it('changes route and active nav state when clicking navigation links', async () => {
    const { container } = renderApp('/history');

    await screen.findAllByText('DailyFX for immich');

    await act(async () => {
      fireEvent.click(container.querySelector('a[href="/schedules"]')!);
    });

    expect(
      await screen.findByRole(
        'heading',
        { name: 'Schedules' },
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();
    expect(container.querySelector('a[href="/schedules"]')).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(window.location.pathname).toBe('/schedules');
  });

  it('keeps the presets subpage when loaded directly', async () => {
    const { container } = renderApp('/presets/effects');

    expect(
      await screen.findByText('No effect presets yet', {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(container.querySelector('a[href="/presets"]')).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(window.location.pathname).toBe('/presets/effects');
  });

  it('supports direct history detail routes', async () => {
    renderApp('/history/man-1');

    expect(
      await screen.findByText('No items found', {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe('/history/man-1');
  });

  it('supports direct schedule creation routes', async () => {
    renderApp('/schedules/new');

    expect(
      await screen.findByRole('button', { name: 'Save' }, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe('/schedules/new');
  });

  it('shows a 404 page for unknown routes', async () => {
    renderApp('/not-a-real-route');

    expect(
      await screen.findByText('Page not found', {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe('/not-a-real-route');
  });

  it('renders Studio navigation link and navigates to Studio page', async () => {
    const { container } = renderApp('/history');

    expect(
      await screen.findAllByText('Studio', {}, { timeout: 5000 }),
    ).not.toHaveLength(0);

    await act(async () => {
      fireEvent.click(container.querySelector('a[href="/studio"]')!);
    });

    expect(
      await screen.findByText('Choose image', {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(container.querySelector('a[href="/studio"]')).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(window.location.pathname).toBe('/studio');
  });
});
