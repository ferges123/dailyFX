import { useEffect, useMemo, useState } from 'react';
import { type GenerationHistoryEntry } from '../../api/client';

const LAST_STARTED_TASK_ID_KEY = 'dailyfx_last_started_task_id';

export function useHistorySelection(filteredHistoryItems: GenerationHistoryEntry[]) {
  const [selectedHistoryTaskId, setSelectedHistoryTaskId] = useState<string | null>(null);
  const [mobileShowDetail, setMobileShowDetail] = useState(false);

  const selectedHistoryEntry = useMemo(
    () => filteredHistoryItems.find((item) => item.task_id === selectedHistoryTaskId) ?? null,
    [filteredHistoryItems, selectedHistoryTaskId],
  );

  useEffect(() => {
    const lastStartedTaskId = sessionStorage.getItem(LAST_STARTED_TASK_ID_KEY);
    if (lastStartedTaskId) {
      const found = filteredHistoryItems.find((item) => item.task_id === lastStartedTaskId);
      if (found) {
        setSelectedHistoryTaskId(lastStartedTaskId);
        sessionStorage.removeItem(LAST_STARTED_TASK_ID_KEY);
        return;
      }
    }
    if (!selectedHistoryTaskId && filteredHistoryItems.length > 0) {
      setSelectedHistoryTaskId(filteredHistoryItems[0].task_id);
    }
  }, [filteredHistoryItems, selectedHistoryTaskId]);

  useEffect(() => {
    if (selectedHistoryTaskId && !filteredHistoryItems.some((item) => item.task_id === selectedHistoryTaskId)) {
      setSelectedHistoryTaskId(filteredHistoryItems[0]?.task_id ?? null);
    }
  }, [filteredHistoryItems, selectedHistoryTaskId]);

  return {
    selectedHistoryTaskId,
    setSelectedHistoryTaskId,
    selectedHistoryEntry,
    mobileShowDetail,
    setMobileShowDetail,
  };
}
