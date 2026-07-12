import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { QueuePage } from '../pages/QueuePage';
import * as queueApi from '../api/queue';

vi.mock('../api/queue', () => {
  return {
    getQueueList: vi.fn(),
    cancelQueueTask: vi.fn(),
    retryQueueTask: vi.fn(),
  };
});

const mockTask: queueApi.QueueItem = {
  task_id: 'task-123',
  status: 'running',
  step: 'generating',
  progress: 0.45,
  priority: 'high',
  attempt: 1,
  created_at: '2026-07-12T12:00:00Z',
};

describe('QueuePage', () => {
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

  function renderQueuePage() {
    return render(
      <QueryClientProvider client={queryClient}>
        <QueuePage />
      </QueryClientProvider>
    );
  }

  it('renders both desktop table and mobile card list classes', async () => {
    vi.mocked(queueApi.getQueueList).mockResolvedValue({
      total: 1,
      items: [mockTask],
    });

    renderQueuePage();

    expect(screen.getByText('Generation Queue')).toBeInTheDocument();

    await waitFor(() => {
      // Find Task ID in desktop table
      expect(screen.getAllByText('task-123').length).toBeGreaterThanOrEqual(1);
    });

    // Verify mobile specific elements exist in the document
    const mobileList = screen.getByLabelText('Generation queue mobile list');
    expect(mobileList).toBeInTheDocument();
    expect(mobileList.className).toContain('md:hidden');
  });

  it('triggers cancel mutation from mobile view', async () => {
    vi.mocked(queueApi.getQueueList).mockResolvedValue({
      total: 1,
      items: [mockTask],
    });
    vi.mocked(queueApi.cancelQueueTask).mockResolvedValue({ message: 'Cancelled' });

    renderQueuePage();

    await waitFor(() => {
      const mobileList = screen.getByLabelText('Generation queue mobile list');
      expect(mobileList).toBeInTheDocument();
    });

    // Find the Cancel buttons (one desktop, one mobile)
    const cancelButtons = screen.getAllByRole('button', { name: /Cancel/i });
    expect(cancelButtons.length).toBe(2); // One in table, one in card

    // Trigger click on the second (mobile card list) cancel button
    fireEvent.click(cancelButtons[1]);

    await waitFor(() => {
      expect(queueApi.cancelQueueTask).toHaveBeenCalledWith('task-123');
    });
  });
});
