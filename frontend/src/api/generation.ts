import {
  request,
  getAuthHeader,
  handleResponseError,
  apiBase,
  ApiError,
} from './base';
import {
  type GenerationModuleInfo,
  type StudioPreviewResponse,
  type GenerationExampleInfo,
  type GenerationHistoryPage,
  type GenerationHistoryEntry,
  type GenerationAcceptRequest,
  type FilterPreset,
  type EffectPreset,
  type AIEffect,
  type AIEffectUpsert,
  type AIEffectImportRequest,
  type AIEffectImportResult,
  type AIEffectExport,
  type Schedule,
  type EffectStats,
} from './types';

export function getGenerationModules() {
  return request<GenerationModuleInfo[]>('/api/generation/modules');
}

export function getStudioModules() {
  return request<GenerationModuleInfo[]>('/api/studio/modules');
}

export async function createStudioPreview(
  file: File,
  effectId: string,
  config: Record<string, unknown>,
  options: {
    aiVisionEnabled?: boolean;
    promptEnrichmentEnabled?: boolean;
  } = {},
): Promise<StudioPreviewResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('effect_id', effectId);
  formData.append('config', JSON.stringify(config));
  formData.append(
    'ai_vision_enabled',
    options.aiVisionEnabled ? 'true' : 'false',
  );
  formData.append(
    'prompt_enrichment_enabled',
    options.promptEnrichmentEnabled ? 'true' : 'false',
  );

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout for preview
  try {
    const response = await fetch(`${apiBase}/api/studio/preview`, {
      signal: controller.signal,
      method: 'POST',
      headers: {
        ...getAuthHeader(),
      },
      body: formData,
    });
    clearTimeout(timeoutId);
    if (!response.ok) {
      await handleResponseError(response);
    }
    return response.json() as Promise<StudioPreviewResponse>;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError(408, 'Studio preview request timed out (60s limit)');
    }
    throw error;
  }
}

export function getGenerationExamples() {
  return request<GenerationExampleInfo[]>('/api/generation/examples');
}

export function getGenerationHistory(
  status?: string,
  offset?: number,
  search?: string,
  limit = 10,
) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (offset !== undefined) params.set('offset', String(offset));
  if (search) params.set('search', search);
  params.set('limit', String(limit));
  const qs = params.toString();
  return request<GenerationHistoryPage>(
    `/api/generation/history${qs ? `?${qs}` : ''}`,
  );
}

export function acceptGeneration(
  taskId: string,
  payload: GenerationAcceptRequest,
) {
  return request<GenerationHistoryEntry>(
    `/api/generation/history/${taskId}/accept`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export function retryGenerationAcceptance(taskId: string) {
  return request<GenerationHistoryEntry>(
    `/api/generation/history/${taskId}/retry`,
    {
      method: 'POST',
    },
  );
}

export function rejectGeneration(taskId: string) {
  return request<GenerationHistoryEntry>(
    `/api/generation/history/${taskId}/reject`,
    {
      method: 'POST',
    },
  );
}

export function clearRejectedCache() {
  return request<void>('/api/generation/history/rejected', {
    method: 'DELETE',
  });
}

export function clearHistoryByStatus(
  status: 'rejected' | 'failed' | 'pending' | 'accepted',
) {
  return request<void>(`/api/generation/history/status/${status}`, {
    method: 'DELETE',
  });
}

export function clearGenerationCache() {
  return request<void>('/api/generation/history/cache', { method: 'DELETE' });
}

export function likeGeneration(taskId: string) {
  return request<GenerationHistoryEntry>(
    `/api/generation/history/${taskId}/like`,
    {
      method: 'POST',
    },
  );
}

export function dislikeGeneration(taskId: string) {
  return request<GenerationHistoryEntry>(
    `/api/generation/history/${taskId}/dislike`,
    {
      method: 'POST',
    },
  );
}

export function getEffectStats() {
  return request<EffectStats[]>('/api/generation/stats/effects');
}


// Filter presets
export const getFilterPresets = () =>
  request<FilterPreset[]>('/api/presets/filters');
export const createFilterPreset = (
  body: Omit<FilterPreset, 'id' | 'created_at'>,
) =>
  request<FilterPreset>('/api/presets/filters', {
    method: 'POST',
    body: JSON.stringify(body),
  });
export const updateFilterPreset = (
  id: number,
  body: Omit<FilterPreset, 'id' | 'created_at'>,
) =>
  request<FilterPreset>(`/api/presets/filters/${id}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
export const deleteFilterPreset = (id: number) =>
  request<void>(`/api/presets/filters/${id}`, { method: 'DELETE' });

// Effect presets
export const getEffectPresets = () =>
  request<EffectPreset[]>('/api/presets/effects');
export const createEffectPreset = (
  body: Omit<EffectPreset, 'id' | 'created_at'>,
) =>
  request<EffectPreset>('/api/presets/effects', {
    method: 'POST',
    body: JSON.stringify(body),
  });
export const updateEffectPreset = (
  id: number,
  body: Omit<EffectPreset, 'id' | 'created_at'>,
) =>
  request<EffectPreset>(`/api/presets/effects/${id}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
export const deleteEffectPreset = (id: number) =>
  request<void>(`/api/presets/effects/${id}`, { method: 'DELETE' });

export function getAIEffects() {
  return request<AIEffect[]>('/api/ai-effects');
}

export function createAIEffect(body: AIEffectUpsert) {
  return request<AIEffect>('/api/ai-effects', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function updateAIEffect(id: string, body: AIEffectUpsert) {
  return request<AIEffect>(`/api/ai-effects/${id}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}

export function deleteAIEffect(id: string) {
  return request<AIEffect>(`/api/ai-effects/${id}`, {
    method: 'DELETE',
  });
}

export function resetAIEffect(id: string) {
  return request<AIEffect>(`/api/ai-effects/${id}/reset`, {
    method: 'POST',
  });
}

export function duplicateAIEffect(id: string) {
  return request<AIEffect>(`/api/ai-effects/${id}/duplicate`, {
    method: 'POST',
  });
}

export function importAIEffects(body: AIEffectImportRequest) {
  return request<AIEffectImportResult>('/api/ai-effects/import', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function exportAIEffects() {
  return request<AIEffectExport>('/api/ai-effects/export');
}

// Schedules
export const getSchedules = () => request<Schedule[]>('/api/schedules');
export const createSchedule = (
  body: Omit<
    Schedule,
    | 'id'
    | 'created_at'
    | 'last_run_at'
    | 'next_run_at'
    | 'last_tick_status'
    | 'last_tick_reason'
    | 'last_task_id'
    | 'filter_preset_name'
    | 'effect_preset_name'
    | 'notification_preset_names'
  >,
) =>
  request<Schedule>('/api/schedules', {
    method: 'POST',
    body: JSON.stringify(body),
  });
export const updateSchedule = (
  id: number,
  body: Omit<
    Schedule,
    | 'id'
    | 'created_at'
    | 'last_run_at'
    | 'next_run_at'
    | 'last_tick_status'
    | 'last_tick_reason'
    | 'last_task_id'
    | 'filter_preset_name'
    | 'effect_preset_name'
    | 'notification_preset_names'
  >,
) =>
  request<Schedule>(`/api/schedules/${id}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
export const deleteSchedule = (id: number) =>
  request<void>(`/api/schedules/${id}`, { method: 'DELETE' });
export const triggerScheduleNow = (id: number) =>
  request<{ message: string; task_id: string }>(
    `/api/schedules/${id}/run-now`,
    { method: 'POST' },
  );
