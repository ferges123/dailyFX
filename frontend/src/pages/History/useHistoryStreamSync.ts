import { useEffect, useState } from 'react';
import { useQueryClient, type InfiniteData } from '@tanstack/react-query';
import {
  type GenerationHistoryListItem,
  type GenerationHistoryPage,
} from '../../api/client';
import {
  openGenerationStream,
  type GenerationStreamConnectionState,
} from '../../api/generationStream';
import {
  updateHistoryCacheForTask,
  updateHistoryCacheForUpsert,
} from './history.utils';

interface UseHistoryStreamSyncParams {
  enabled: boolean;
  historyQueryKey: readonly unknown[];
  streamCursor: number;
  statusParam: string | undefined;
  debouncedSearch: string;
}

export function useHistoryStreamSync({
  enabled,
  historyQueryKey,
  streamCursor,
  statusParam,
  debouncedSearch,
}: UseHistoryStreamSyncParams) {
  const queryClient = useQueryClient();
  const [streamStatus, setStreamStatus] =
    useState<GenerationStreamConnectionState>('disconnected');

  useEffect(() => {
    if (!enabled) return;

    const stream = openGenerationStream({
      lastEventId: streamCursor,
      onStatus: setStreamStatus,
      onResyncRequired: () => {
        queryClient.invalidateQueries({ queryKey: historyQueryKey });
      },
      onEvent: (event) => {
        if (event.event === 'history-upsert') {
          const payload = event.data as GenerationHistoryListItem;
          if (!payload?.task_id) return;
          queryClient.setQueryData<InfiniteData<GenerationHistoryPage>>(
            historyQueryKey,
            (oldData) =>
              updateHistoryCacheForUpsert(
                oldData,
                payload,
                statusParam,
                debouncedSearch,
              ),
          );
          queryClient.invalidateQueries({
            queryKey: ['generation-history-detail', payload.task_id],
          });
          return;
        }

        if (event.event === 'task-upsert') {
          const payload = event.data as { task_id?: string } | null;
          if (payload?.task_id) {
            queryClient.invalidateQueries({
              queryKey: ['generation-history-detail', payload.task_id],
            });
          }
          queryClient.setQueryData<InfiniteData<GenerationHistoryPage>>(
            historyQueryKey,
            (oldData) =>
              updateHistoryCacheForTask(
                oldData,
                event,
                statusParam,
                debouncedSearch,
              ),
          );
        }
      },
    });

    return () => {
      stream.close();
    };
  }, [
    debouncedSearch,
    enabled,
    historyQueryKey,
    queryClient,
    statusParam,
    streamCursor,
  ]);

  return { streamStatus, setStreamStatus };
}
