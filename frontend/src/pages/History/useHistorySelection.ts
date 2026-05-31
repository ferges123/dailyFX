import { useEffect, useMemo, useState } from 'react';
import { type GenerationHistoryEntry } from '../../api/client';

const LAST_STARTED_TASK_ID_KEY = 'dailyfx_last_started_task_id';

export function useHistorySelection(
  filteredHistoryItems: GenerationHistoryEntry[],
  selectedHistoryTaskId: string | null,
  setSelectedHistoryTaskId: (taskId: string | null) => void,
  allowFallbackSelection = true,
) {
  const [mobileShowDetail, setMobileShowDetail] = useState(false);

  const selectedHistoryEntry = useMemo(
    () => filteredHistoryItems.find((item) => item.task_id === selectedHistoryTaskId) ?? null,
    [filteredHistoryItems, selectedHistoryTaskId],
  );

  useEffect(() => {
    if (allowFallbackSelection && !selectedHistoryTaskId && filteredHistoryItems.length > 0) {
      const lastStartedTaskId = sessionStorage.getItem(LAST_STARTED_TASK_ID_KEY);
      if (lastStartedTaskId) {
        const found = filteredHistoryItems.find((item) => item.task_id === lastStartedTaskId);
        if (found) {
          setSelectedHistoryTaskId(lastStartedTaskId);
          sessionStorage.removeItem(LAST_STARTED_TASK_ID_KEY);
          return;
        }
      }
      setSelectedHistoryTaskId(filteredHistoryItems[0].task_id);
    }
  }, [allowFallbackSelection, filteredHistoryItems, selectedHistoryTaskId, setSelectedHistoryTaskId]);

  useEffect(() => {
    if (selectedHistoryTaskId && !filteredHistoryItems.some((item) => item.task_id === selectedHistoryTaskId)) {
      setSelectedHistoryTaskId(allowFallbackSelection ? (filteredHistoryItems[0]?.task_id ?? null) : null);
    }
  }, [allowFallbackSelection, filteredHistoryItems, selectedHistoryTaskId, setSelectedHistoryTaskId]);

  return {
    selectedHistoryEntry,
    mobileShowDetail,
    setMobileShowDetail,
  };
}
