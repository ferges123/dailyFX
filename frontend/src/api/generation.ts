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
  type ScheduleDiagnosticsResponse,
  type EffectStats,
  type TrendsResponse,
} from './types';

export function getGenerationModules() {
  return request<GenerationModuleInfo[]>('/api/generation/modules');
}

export function getStudioModules() {
  return request<GenerationModuleInfo[]>('/api/studio/modules');
}

type StudioPreviewOptions = {
  aiVisionEnabled?: boolean;
  promptEnrichmentEnabled?: boolean;
};

async function requestStudioPreview(
  path: string,
  body: BodyInit,
  headers: Record<string, string> = {},
): Promise<StudioPreviewResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch(`${apiBase}${path}`, {
      signal: controller.signal,
      method: 'POST',
      headers: {
        ...getAuthHeader(),
        ...headers,
      },
      body,
    });
    if (!response.ok) {
      await handleResponseError(response);
    }
    return response.json() as Promise<StudioPreviewResponse>;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError(408, 'Studio preview request timed out (60s limit)');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function createStudioPreview(
  file: File,
  effectId: string,
  config: Record<string, unknown>,
  options: StudioPreviewOptions = {},
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

  return requestStudioPreview('/api/studio/preview', formData);
}

export async function createStudioPreviewFromImmich(
  assetId: string,
  effectId: string,
  config: Record<string, unknown>,
  options: StudioPreviewOptions = {},
): Promise<StudioPreviewResponse> {
  return requestStudioPreview(
    '/api/studio/preview/immich',
    JSON.stringify({
      asset_id: assetId,
      effect_id: effectId,
      config,
      ai_vision_enabled: options.aiVisionEnabled ?? false,
      prompt_enrichment_enabled: options.promptEnrichmentEnabled ?? false,
    }),
    { 'Content-Type': 'application/json' },
  );
}

export function getGenerationExamples() {
  return request<GenerationExampleInfo[]>('/api/generation/examples');
}

export function getGenerationHistory(
  status?: string,
  offset?: number,
  search?: string,
  limit = 10,
  options: {
    effect?: string | null;
    liked?: boolean | null;
    sort?: 'newest' | 'oldest';
  } = {},
) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (offset !== undefined) params.set('offset', String(offset));
  if (search) params.set('search', search);
  if (options.effect) params.set('effect', options.effect);
  if (options.liked !== undefined && options.liked !== null) {
    params.set('liked', String(options.liked));
  }
  if (options.sort) params.set('sort', options.sort);
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

export function clearHistoryByStatus(
  status: 'rejected' | 'failed' | 'pending' | 'accepted' | 'running',
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

export function getStatsTrends() {
  return request<TrendsResponse>('/api/generation/stats/trends');
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
export const getScheduleDiagnostics = (id: number) =>
  request<ScheduleDiagnosticsResponse>(`/api/schedules/${id}/diagnostics`);
