import { render, screen } from '@testing-library/react';
import { test, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { SystemPage } from '../pages/SystemPage';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as client from '../api/client';

vi.mock('../api/client', () => ({
  getEffectStats: vi.fn(),
  getStatsTrends: vi.fn(),
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(client.getEffectStats).mockResolvedValue([]);
  vi.mocked(client.getStatsTrends).mockResolvedValue({ daily: [], weekly: [] });
});

test('renders system page tab options', () => {
    render(
        <QueryClientProvider client={queryClient}>
            <MemoryRouter initialEntries={['/system/statistics']}>
                <SystemPage />
            </MemoryRouter>
        </QueryClientProvider>
    );
    expect(screen.getByText(/Statistics/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Generation Queue/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Audit Log/i)).toBeInTheDocument();
});
