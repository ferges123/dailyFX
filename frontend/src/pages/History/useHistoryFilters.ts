import { useMemo, useState } from 'react';
import { type HistoryStatusFilter } from '../history.types';
import { historyStatusToStatusParam } from './history.utils';
import { useDebounce } from './useDebounce';

export function useHistoryFilters() {
  const [historySearch, setHistorySearch] = useState('');
  const debouncedSearch = useDebounce(historySearch, 300);
  const [historyStatus, setHistoryStatus] =
    useState<HistoryStatusFilter>('all');

  const statusParam = useMemo(
    () => historyStatusToStatusParam(historyStatus),
    [historyStatus],
  );

  return {
    historySearch,
    setHistorySearch,
    debouncedSearch,
    historyStatus,
    setHistoryStatus,
    statusParam,
  };
}
