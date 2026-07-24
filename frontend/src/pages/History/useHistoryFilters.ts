import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import { type HistoryStatusFilter } from '../history.types';
import { historyStatusToStatusParam } from './history.utils';
import { useDebounce } from './useDebounce';

export function useHistoryFilters() {
  const [searchParams] = useSearchParams();
  const searchParam = searchParams.get('search') || '';
  const [historySearch, setHistorySearch] = useState(searchParam);
  const debouncedSearch = useDebounce(historySearch, 300);
  const [historyStatus, setHistoryStatus] =
    useState<HistoryStatusFilter>('all');

  useEffect(() => {
    setHistorySearch(searchParam);
  }, [searchParam]);

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
