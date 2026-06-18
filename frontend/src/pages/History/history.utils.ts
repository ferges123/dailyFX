import { type InfiniteData } from '@tanstack/react-query';
import {
  type GenerationHistoryEntry,
  type GenerationHistoryPage,
} from '../../api/client';
import { type GenerationStreamEvent } from '../../api/generationStream';
import { type HistoryStatusFilter } from '../history.types';

export const HISTORY_PAGE_LIMIT = 10;

export function matchesHistoryFilters(
  item: GenerationHistoryEntry,
  statusParam: string | undefined,
  search: string,
): boolean {
  if (statusParam && item.status !== statusParam) {
    return false;
  }

  const needle = search.trim().toLowerCase();
  if (!needle) {
    return true;
  }

  return [
    item.title,
    item.summary,
    item.generation_type,
    item.provider,
    item.model,
    item.album_name,
  ].some((value) => (value ?? '').toLowerCase().includes(needle));
}

export function updateHistoryCacheForUpsert(
  oldData: InfiniteData<GenerationHistoryPage> | undefined,
  entry: GenerationHistoryEntry,
  statusParam: string | undefined,
  search: string,
): InfiniteData<GenerationHistoryPage> | undefined {
  if (!oldData) return oldData;

  const pages = oldData.pages.map((page) => ({
    ...page,
    items: page.items.map((item) => ({ ...item })),
  }));
  let found = false;

  for (const page of pages) {
    const index = page.items.findIndex(
      (item) => item.task_id === entry.task_id,
    );
    if (index < 0) continue;

    found = true;
    const merged = { ...page.items[index], ...entry };
    if (matchesHistoryFilters(merged, statusParam, search)) {
      page.items[index] = merged;
    } else {
      page.items.splice(index, 1);
      page.total = Math.max(0, page.total - 1);
    }
    break;
  }

  if (!found && matchesHistoryFilters(entry, statusParam, search)) {
    if (pages.length === 0) {
      pages.push({
        items: [entry],
        total: 1,
        latest_event_id: oldData.pages[0]?.latest_event_id ?? 0,
      });
    } else {
      pages[0] = {
        ...pages[0],
        items: [
          entry,
          ...pages[0].items.filter((item) => item.task_id !== entry.task_id),
        ].slice(0, HISTORY_PAGE_LIMIT),
        total: pages[0].total + 1,
      };
    }
  }

  return {
    ...oldData,
    pages,
  };
}

export function updateHistoryCacheForTask(
  oldData: InfiniteData<GenerationHistoryPage> | undefined,
  event: GenerationStreamEvent,
  statusParam: string | undefined,
  search: string,
): InfiniteData<GenerationHistoryPage> | undefined {
  if (!oldData || !event || event.event !== 'task-upsert') return oldData;
  const payload = event.data as {
    task_id?: string;
    status?: string;
    step?: string | null;
    progress?: number | null;
    error?: string | null;
  } | null;

  if (!payload?.task_id) return oldData;

  const pages = oldData.pages.map((page) => ({
    ...page,
    items: page.items.map((item) => ({ ...item })),
  }));

  for (const page of pages) {
    const index = page.items.findIndex(
      (item) => item.task_id === payload.task_id,
    );
    if (index < 0) continue;

    const current = page.items[index];
    const nextStatus =
      payload.status === 'failed'
        ? 'FAILED'
        : payload.status === 'running' && current.status === 'RUNNING'
          ? 'RUNNING'
          : current.status;
    const merged: GenerationHistoryEntry = {
      ...current,
      status: nextStatus,
      task_step: payload.step ?? current.task_step,
    };

    if (matchesHistoryFilters(merged, statusParam, search)) {
      page.items[index] = merged;
    } else {
      page.items.splice(index, 1);
      page.total = Math.max(0, page.total - 1);
    }
    break;
  }

  return {
    ...oldData,
    pages,
  };
}

export function historyStatusToStatusParam(
  historyStatus: HistoryStatusFilter,
): string | undefined {
  return historyStatus === 'generated'
    ? 'PENDING_REVIEW'
    : historyStatus === 'uploaded'
      ? 'UPLOADED'
      : historyStatus === 'failed'
        ? 'FAILED'
        : historyStatus === 'rejected'
          ? 'REJECTED'
          : undefined;
}
