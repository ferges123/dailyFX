import { useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import {
  getGenerationHistory,
  type GenerationHistoryPage,
} from '../../api/client';
import { HISTORY_PAGE_LIMIT } from './history.utils';

export function useHistoryQuery(
  statusParam: string | undefined,
  debouncedSearch: string,
) {
  const historyQueryKey = useMemo(
    () => ['generation-history', statusParam, debouncedSearch] as const,
    [statusParam, debouncedSearch],
  );

  const historyQuery = useInfiniteQuery({
    queryKey: historyQueryKey,
    queryFn: ({ pageParam = 0 }) =>
      getGenerationHistory(
        statusParam,
        pageParam,
        debouncedSearch,
        HISTORY_PAGE_LIMIT,
      ),
    initialPageParam: 0,
    getNextPageParam: (lastPage: GenerationHistoryPage, allPages) => {
      const nextOffset = allPages.length * HISTORY_PAGE_LIMIT;
      return nextOffset < lastPage.total ? nextOffset : undefined;
    },
  });

  const filteredHistoryItems = useMemo(() => {
    return historyQuery.data?.pages.flatMap((page) => page.items) ?? [];
  }, [historyQuery.data]);

  const streamCursor = useMemo(
    () => historyQuery.data?.pages[0]?.latest_event_id ?? 0,
    [historyQuery.data],
  );

  return {
    historyQueryKey,
    filteredHistoryItems,
    streamCursor,
    ...historyQuery,
  };
}
