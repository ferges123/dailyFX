import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useHistoryFilters } from '../pages/History/useHistoryFilters';
import { useHistorySelection } from '../pages/History/useHistorySelection';
import { useHistoryStreamSync } from '../pages/History/useHistoryStreamSync';
import { openGenerationStream } from '../api/generationStream';
import React from 'react';
import { type GenerationHistoryEntry } from '../api/client';
import { MemoryRouter } from 'react-router';

vi.mock('../api/generationStream', () => {
  return {
    openGenerationStream: vi.fn(() => ({
      close: vi.fn(),
    })),
  };
});

const createWrapper = () => {
  const queryClient = new QueryClient();
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('useHistoryFilters', () => {
  it('initializes and updates search filters correctly', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter>{children}</MemoryRouter>
    );
    const { result } = renderHook(() => useHistoryFilters(), { wrapper });

    expect(result.current.historyStatus).toBe('all');
    expect(result.current.historySearch).toBe('');
    expect(result.current.statusParam).toBeUndefined();

    act(() => {
      result.current.setHistoryStatus('uploaded');
      result.current.setHistorySearch('sunset');
    });

    expect(result.current.historyStatus).toBe('uploaded');
    expect(result.current.historySearch).toBe('sunset');
    expect(result.current.statusParam).toBe('UPLOADED');
  });
});

describe('useHistorySelection', () => {
  it('manages fallback selection and detail panel state', () => {
    const mockItems = [
      { task_id: 'task-1', title: 'Generation 1' },
      { task_id: 'task-2', title: 'Generation 2' },
    ] as unknown as GenerationHistoryEntry[];

    const setSelectedHistoryTaskId = vi.fn();

    renderHook(
      ({ items, taskId }) =>
        useHistorySelection(items, taskId, setSelectedHistoryTaskId),
      {
        initialProps: {
          items: mockItems,
          taskId: null as string | null,
        },
      },
    );

    // Because allowFallbackSelection is true (default), the hook should auto-select the first item
    expect(setSelectedHistoryTaskId).toHaveBeenCalledWith('task-1');
  });
});

describe('useHistoryStreamSync', () => {
  it('opens generation stream and configures query invalidation', () => {
    renderHook(
      () =>
        useHistoryStreamSync({
          enabled: true,
          historyQueryKey: ['history'],
          streamCursor: 1,
          statusParam: 'UPLOADED',
          debouncedSearch: '',
        }),
      {
        wrapper: createWrapper(),
      },
    );

    expect(openGenerationStream).toHaveBeenCalled();
  });
});
