import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AuditLogPage from '../pages/AuditLog/AuditLogPage';
import * as client from '../api/client';

vi.mock('../api/client', () => {
  return {
    getAuditLogs: vi.fn(),
    downloadAuditExport: vi.fn(),
  };
});

const mockEvent = {
  event_id: 'evt-1',
  occurred_at: '2026-07-11T12:00:00Z',
  action: 'settings.updated',
  category: 'settings',
  outcome: 'success',
  actor_type: 'user',
  summary: 'Settings updated successfully',
  changes: {
    ai_vision_hourly_limit: { from: 10, to: 20 },
  },
  metadata: {
    ip: '127.0.0.1',
  },
};

describe('AuditLogPage', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    vi.clearAllMocks();
  });

  function renderAuditLog() {
    return render(
      <QueryClientProvider client={queryClient}>
        <AuditLogPage />
      </QueryClientProvider>
    );
  }

  it('renders and displays audit events', async () => {
    vi.mocked(client.getAuditLogs).mockResolvedValue({
      events: [mockEvent],
      total: 1,
      limit: 25,
      offset: 0,
    });

    renderAuditLog();

    expect(screen.getByText('System Audit Log')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('settings.updated')).toBeInTheDocument();
      expect(screen.getByText('Settings updated successfully')).toBeInTheDocument();
    });
  });

  it('filters trigger audit search refetch', async () => {
    vi.mocked(client.getAuditLogs).mockResolvedValue({
      events: [mockEvent],
      total: 1,
      limit: 25,
      offset: 0,
    });

    renderAuditLog();

    await waitFor(() => {
      expect(screen.getByText('settings.updated')).toBeInTheDocument();
    });

    const actionInput = screen.getByPlaceholderText('e.g. settings.updated');
    fireEvent.change(actionInput, { target: { value: 'generation.started' } });

    expect(client.getAuditLogs).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'generation.started',
      })
    );
  });

  it('opens details modal when clicking row', async () => {
    vi.mocked(client.getAuditLogs).mockResolvedValue({
      events: [mockEvent],
      total: 1,
      limit: 25,
      offset: 0,
    });

    renderAuditLog();

    await waitFor(() => {
      expect(screen.getByText('settings.updated')).toBeInTheDocument();
    });

    const row = screen.getByText('Settings updated successfully');
    fireEvent.click(row);

    expect(screen.getByText('Event: evt-1')).toBeInTheDocument();
    expect(screen.getByText('ai_vision_hourly_limit')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('20')).toBeInTheDocument();
  });

  it('triggers download when export buttons are clicked', async () => {
    vi.mocked(client.getAuditLogs).mockResolvedValue({
      events: [mockEvent],
      total: 1,
      limit: 25,
      offset: 0,
    });

    renderAuditLog();

    const csvButton = screen.getByRole('button', { name: /Export CSV/i });
    fireEvent.click(csvButton);

    expect(client.downloadAuditExport).toHaveBeenCalledWith(
      expect.objectContaining({
        format: 'csv',
      })
    );
  });
});
