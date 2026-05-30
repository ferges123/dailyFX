import { useEffect, useState } from 'react';
import { useQueryClient, type InfiniteData } from '@tanstack/react-query';
import { type GenerationHistoryEntry, type GenerationHistoryPage } from '../../api/client';
import { openGenerationStream, type GenerationStreamConnectionState, type GenerationStreamEvent } from '../../api/generationStream';
import { updateHistoryCacheForTask, updateHistoryCacheForUpsert } from './history.utils';

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
  const [streamStatus, setStreamStatus] = useState<GenerationStreamConnectionState>('disconnected');

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
          const payload = event.data as GenerationHistoryEntry;
          if (!payload?.task_id) return;
          queryClient.setQueryData<InfiniteData<GenerationHistoryPage>>(historyQueryKey, (oldData) =>
            updateHistoryCacheForUpsert(oldData, payload, statusParam, debouncedSearch),
          );
          return;
        }

        if (event.event === 'task-upsert') {
          queryClient.setQueryData<InfiniteData<GenerationHistoryPage>>(historyQueryKey, (oldData) =>
            updateHistoryCacheForTask(oldData, event, statusParam, debouncedSearch),
          );
        }
      },
    });

    return () => {
      stream.close();
    };
  }, [debouncedSearch, enabled, historyQueryKey, queryClient, statusParam, streamCursor]);

  return { streamStatus, setStreamStatus };
}
