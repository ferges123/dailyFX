export type Settings = {
  immich_url: string | null;
  local_ai_base_url: string | null;
  ai_vision_hourly_limit: number;
  ai_image_hourly_limit: number;
  debug_mode: boolean;
  favorite_albums_json: string | null;
  ai_custom_prompt: string | null;
  immich_api_key_masked: string | null;
  openai_api_key_masked: string | null;
  gemini_api_key_masked: string | null;
  openrouter_api_key_masked: string | null;
  byteplus_api_key_masked: string | null;
  xiaomi_api_key_masked: string | null;
  local_ai_api_key_masked: string | null;
};

export type HealthCheckStatus = {
  status: string;
  detail?: string | null;
  age_seconds?: number | null;
  version?: string | null;
  user?: string | null;
  provider?: string | null;
  http?: number | null;
  server_url?: string | null;
  user_email?: string | null;
  user_id?: string | null;
  server_version?: string | null;
};

export type DetailedHealth = {
  status: string;
  checks: Record<string, HealthCheckStatus>;
};

export type SettingsUpdate = Omit<
  Settings,
  | 'immich_api_key_masked'
  | 'openai_api_key_masked'
  | 'gemini_api_key_masked'
  | 'openrouter_api_key_masked'
  | 'byteplus_api_key_masked'
  | 'xiaomi_api_key_masked'
  | 'local_ai_api_key_masked'
> & {
  immich_api_key?: string | null;
  openai_api_key?: string | null;
  gemini_api_key?: string | null;
  openrouter_api_key?: string | null;
  byteplus_api_key?: string | null;
  xiaomi_api_key?: string | null;
  local_ai_api_key?: string | null;
};

export type ConnectionTest = {
  ok: boolean;
  message: string;
  provider: string;
  detail: string | null;
  model: string | null;
  server_url: string | null;
  user_email: string | null;
  user_id: string | null;
  server_version: string | null;
};

export type ImmichAsset = {
  id: string;
  original_file_name: string | null;
  created_at: string | null;
  updated_at: string | null;
  mime_type: string | null;
  asset_type: string | null;
  people: ImmichPerson[];
};

export type ImmichAssetPage = {
  items: ImmichAsset[];
  total: number | null;
  count: number | null;
  next_page: string | null;
};

export type ImmichAlbum = {
  id: string;
  album_name: string;
  asset_count: number;
  thumbnail_asset_id: string | null;
};

export type ImmichPerson = {
  id: string;
  name: string;
  is_hidden: boolean;
  asset_count: number;
};

export type ImmichPersonFilter = {
  personId: string;
  mode: 'optional' | 'obligatory' | 'exclude';
};

export type ImmichFilterOptions = {
  albums: ImmichAlbum[];
  people: ImmichPerson[];
};

export type GenerationModuleInfo = {
  name: string;
  label: string;
  description: string;
  default_weight: number;
  default_config: Record<string, unknown>;
  config_schema: GenerationModuleConfigField[];
};

export type GenerationExampleInfo = {
  module_name: string;
  label: string;
  title: string;
  summary: string;
  source_asset_id: string;
  image_url: string;
};

export type GenerationModuleConfigOption = {
  label: string;
  value: string;
};

export type GenerationModuleConfigField = {
  key: string;
  label: string;
  type: 'select' | 'multiselect' | 'number' | 'text';
  description?: string | null;
  default?: unknown;
  options?: GenerationModuleConfigOption[];
  min?: number | null;
  max?: number | null;
  step?: number | null;
  placeholder?: string | null;
};

export type ImmichAssetSearchFilters = {
  albumIds: string[];
  personFilters: ImmichPersonFilter[];
  startDate: string | null;
  endDate: string | null;
  mediaType: 'all' | 'photo' | 'video';
};

function resolveApiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configured) return configured.replace(/\/$/, '');
  return '';
}

const apiBase = resolveApiBase();

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('dailyfx_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.name = 'ApiError';
  }
}

let onUnauthorizedCallback: (() => void) | null = null;
export function registerOnUnauthorized(cb: () => void) {
  onUnauthorizedCallback = cb;
}

export function getApiUrl(path: string) {
  return `${apiBase}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
      ...init?.headers,
    },
    ...init,
  });
  if (!response.ok) {
    let detail = `API request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // ignore
    }
    if (response.status === 401) {
      onUnauthorizedCallback?.();
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) {
    return {} as T;
  }
  return response.json() as Promise<T>;
}

export function getHealth() {
  return request<{ status: string; version: string; auth_enabled: boolean }>('/api/health');
}

export function getDetailedHealth() {
  return request<DetailedHealth>('/api/health/detailed');
}

export function getSettings() {
  return request<Settings>('/api/settings');
}

export function updateSettings(payload: SettingsUpdate) {
  return request<Settings>('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function testImmichConnection() {
  return request<ConnectionTest>('/api/settings/test-immich', {
    method: 'POST',
  });
}

export function testOpenAIConnection() {
  return request<ConnectionTest>('/api/settings/test-openai', {
    method: 'POST',
  });
}

export function testGeminiConnection() {
  return request<ConnectionTest>('/api/settings/test-gemini', {
    method: 'POST',
  });
}

export function testOpenRouterConnection() {
  return request<ConnectionTest>('/api/settings/test-openrouter', {
    method: 'POST',
  });
}

export function testBytePlusConnection() {
  return request<ConnectionTest>('/api/settings/test-byteplus', {
    method: 'POST',
  });
}

export function testXiaomiConnection() {
  return request<ConnectionTest>('/api/settings/test-xiaomi', {
    method: 'POST',
  });
}

export function testLocalAIConnection() {
  return request<ConnectionTest>('/api/settings/test-local-ai', {
    method: 'POST',
  });
}

export function getImmichFilterOptions() {
  return request<ImmichFilterOptions>('/api/immich/options');
}

export function getGenerationModules() {
  return request<GenerationModuleInfo[]>('/api/generation/modules');
}

export function getGenerationExamples() {
  return request<GenerationExampleInfo[]>('/api/generation/examples');
}


export function getImmichAssetThumbnailUrl(assetId: string, size = 'preview') {
  return getApiUrl(`/api/immich/assets/${assetId}/thumbnail?size=${size}`);
}

export type ImmichAssetExif = {
  make?: string | null;
  model?: string | null;
  lensModel?: string | null;
  exposureTime?: number | string | null;
  fNumber?: number | null;
  iso?: number | null;
  focalLength?: number | null;
  fileSizeInByte?: number | null;
  exifImageWidth?: number | null;
  exifImageHeight?: number | null;
  dateTimeOriginal?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  [key: string]: unknown;
};

export function getImmichAssetExif(assetId: string) {
  return request<ImmichAssetExif>(`/api/immich/assets/${assetId}/exif`);
}

export function getImmichAssetDetailUrl(immichUrl: string | null | undefined, assetId: string | null | undefined) {
  if (!immichUrl || !assetId) return null;
  const base = immichUrl.replace(/\/$/, '');
  return `${base}/photos/${assetId}`;
}

export type GenerationHistoryEntry = {
  id: number;
  task_id: string;
  generation_type: string;
  status: 'QUEUED' | 'RUNNING' | 'PENDING_REVIEW' | 'UPLOADED' | 'REJECTED' | 'FAILED' | string;
  title: string;
  summary: string;
  source_asset_ids: string;
  output_path: string | null;
  image_url: string | null;
  provider: string | null;
  model: string | null;
  total_token_count: number | null;
  config_json: string;
  tags_json: string | null;
  task_step: string | null;
  uploaded_asset_id: string | null;
  upload_status: string | null;
  album_id: string | null;
  album_name: string | null;
  album_created: boolean;
  album_updated: boolean;
  accept_notes: string | null;
  accepted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type GenerationAcceptRequest = {
  create_album: boolean;
  album_name: string | null;
  album_id: string | null;
};


export type GenerationHistoryPage = {
  items: GenerationHistoryEntry[];
  total: number;
  latest_event_id: number;
};

export function getGenerationHistory(status?: string, offset?: number, search?: string, limit = 10) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (offset !== undefined) params.set('offset', String(offset));
  if (search) params.set('search', search);
  params.set('limit', String(limit));
  const qs = params.toString();
  return request<GenerationHistoryPage>(`/api/generation/history${qs ? `?${qs}` : ''}`);
}

export function acceptGeneration(taskId: string, payload: GenerationAcceptRequest) {
  return request<GenerationHistoryEntry>(`/api/generation/history/${taskId}/accept`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function retryGenerationAcceptance(taskId: string) {
  return request<GenerationHistoryEntry>(`/api/generation/history/${taskId}/retry`, {
    method: 'POST',
  });
}

export function rejectGeneration(taskId: string) {
  return request<GenerationHistoryEntry>(`/api/generation/history/${taskId}/reject`, {
    method: 'POST',
  });
}

export async function getVapidPublicKey(): Promise<string> {
  const data = await request<{ publicKey: string }>('/api/notifications/vapid-public-key');
  return data.publicKey;
}

export async function subscribeWebPush(subscription: PushSubscription): Promise<void> {
  const key = subscription.getKey('p256dh');
  const auth = subscription.getKey('auth');
  const userAgent = navigator.userAgent;
  const deviceLabel = buildPushSubscriptionLabel(userAgent);
  await request('/api/notifications/subscribe', {
    method: 'POST',
    body: JSON.stringify({
      endpoint: subscription.endpoint,
      p256dh: key ? btoa(String.fromCharCode(...new Uint8Array(key))) : '',
      auth: auth ? btoa(String.fromCharCode(...new Uint8Array(auth))) : '',
      device_label: deviceLabel,
      user_agent: userAgent,
    }),
  });
}

export async function unsubscribeWebPush(subscription: PushSubscription): Promise<void> {
  const key = subscription.getKey('p256dh');
  const auth = subscription.getKey('auth');
  await request('/api/notifications/unsubscribe', {
    method: 'POST',
    body: JSON.stringify({
      endpoint: subscription.endpoint,
      p256dh: key ? btoa(String.fromCharCode(...new Uint8Array(key))) : '',
      auth: auth ? btoa(String.fromCharCode(...new Uint8Array(auth))) : '',
    }),
  });
}

export type PushSubscriptionInfo = {
  id: number;
  endpoint_preview: string;
  device_label: string | null;
  user_agent: string | null;
  created_at: string;
};

export async function getPushSubscriptions(): Promise<{ count: number; subscriptions: PushSubscriptionInfo[] }> {
  return request('/api/notifications/subscriptions');
}

export async function deletePushSubscription(id: number): Promise<void> {
  await request(`/api/notifications/subscriptions/${id}`, { method: 'DELETE' });
}

function buildPushSubscriptionLabel(userAgent: string): string {
  const platform = getPlatformLabel(userAgent);
  const browser = getBrowserLabel(userAgent);
  return `${platform} ${browser}`.trim();
}

function getPlatformLabel(userAgent: string): string {
  const ua = userAgent.toLowerCase();
  if (ua.includes('android')) {
    const match = userAgent.match(/Android\s+([0-9._]+)/i);
    return match?.[1] ? `Android ${match[1].split('.')[0]}` : 'Android';
  }
  if (ua.includes('iphone')) return 'iPhone';
  if (ua.includes('ipad')) return 'iPad';
  if (ua.includes('windows')) return 'Windows';
  if (ua.includes('mac os x')) return 'Mac';
  if (ua.includes('linux')) return 'Linux';
  if (ua.includes('cros')) return 'ChromeOS';
  return 'Device';
}

function getBrowserLabel(userAgent: string): string {
  const ua = userAgent.toLowerCase();
  if (ua.includes('edg/')) return 'Edge';
  if (ua.includes('opr/') || ua.includes('opera')) return 'Opera';
  if (ua.includes('firefox/')) return 'Firefox';
  if (ua.includes('samsungbrowser/')) return 'Samsung Internet';
  if (ua.includes('crios/')) return 'Chrome';
  if (ua.includes('chrome/')) return 'Chrome';
  if (ua.includes('safari/')) return 'Safari';
  return 'Browser';
}


// ── Presets ───────────────────────────────────────────────────────────────────

export type FilterPreset = {
  id: number;
  name: string;
  album_ids: string[];
  person_filters: { personId: string; mode: string }[];
  start_date: string | null;
  end_date: string | null;
  media_type: string;
  created_at: string;
};

export type EffectPreset = {
  id: number;
  name: string;
  groups: Record<string, { enabled: boolean; weight: number; config: Record<string, unknown> }>;
  created_at: string;
};

export type AIEffect = {
  id: string;
  title: string;
  description: string | null;
  display_group: string | null;
  positive_prompt: string;
  negative_prompt: string | null;
  custom_prompt_placeholder: string | null;
  enabled: boolean;
  source: 'builtin' | 'custom' | 'imported';
  hidden: boolean;
  builtin_hash: string | null;
  latest_builtin_hash: string | null;
  user_modified_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AIEffectUpsert = {
  id: string;
  title: string;
  description: string | null;
  display_group: string | null;
  positive_prompt: string;
  negative_prompt: string | null;
  custom_prompt_placeholder: string | null;
  enabled: boolean;
};

export type AIEffectImportItem = AIEffectUpsert & {
  source?: 'builtin' | 'custom' | 'imported' | null;
};

export type AIEffectImportRequest = {
  schema_version: number;
  overwrite_existing: boolean;
  effects: AIEffectImportItem[];
};

export type AIEffectImportResult = {
  added: string[];
  updated: string[];
  skipped: string[];
  conflicts: string[];
  invalid: string[];
};

export type AIEffectExport = {
  schema_version: number;
  effects: AIEffect[];
};

export type NotificationPreset = {
  id: number;
  name: string;
  provider: string;
  url: string | null;
  topic: string | null;
  has_token: boolean;
  token_masked: string | null;
  webhook_url: string | null;
  created_at: string;
};

export type Schedule = {
  id: number;
  name: string;
  enabled: boolean;
  schedule_expr: string;
  filter_preset_id: number;
  effect_preset_id: number;
  notification_preset_ids: number[];
  album_name: string;
  ai_vision_provider: string;
  ai_vision_model: string;
  ai_image_provider: string;
  ai_image_model: string;
  ai_prompt_enrichment: boolean;
  ai_photo_selection_enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  last_tick_status: string | null;
  last_tick_reason: string | null;
  last_task_id: string | null;
  created_at: string;
  filter_preset_name: string | null;
  effect_preset_name: string | null;
  notification_preset_names: string[];
};

// Filter presets
export const getFilterPresets = () => request<FilterPreset[]>('/api/presets/filters');
export const createFilterPreset = (body: Omit<FilterPreset, 'id' | 'created_at'>) =>
  request<FilterPreset>('/api/presets/filters', { method: 'POST', body: JSON.stringify(body) });
export const updateFilterPreset = (id: number, body: Omit<FilterPreset, 'id' | 'created_at'>) =>
  request<FilterPreset>(`/api/presets/filters/${id}`, { method: 'PUT', body: JSON.stringify(body) });
export const deleteFilterPreset = (id: number) =>
  request<void>(`/api/presets/filters/${id}`, { method: 'DELETE' });

// Effect presets
export const getEffectPresets = () => request<EffectPreset[]>('/api/presets/effects');
export const createEffectPreset = (body: Omit<EffectPreset, 'id' | 'created_at'>) =>
  request<EffectPreset>('/api/presets/effects', { method: 'POST', body: JSON.stringify(body) });
export const updateEffectPreset = (id: number, body: Omit<EffectPreset, 'id' | 'created_at'>) =>
  request<EffectPreset>(`/api/presets/effects/${id}`, { method: 'PUT', body: JSON.stringify(body) });
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

// Notification presets
export const getNotificationPresets = () => request<NotificationPreset[]>('/api/presets/notifications');
export const createNotificationPreset = (body: { name: string; provider: string; url?: string | null; topic?: string | null; token?: string | null; webhook_url?: string | null }) =>
  request<NotificationPreset>('/api/presets/notifications', { method: 'POST', body: JSON.stringify(body) });
export const updateNotificationPreset = (id: number, body: { name: string; provider: string; url?: string | null; topic?: string | null; token?: string | null; webhook_url?: string | null }) =>
  request<NotificationPreset>(`/api/presets/notifications/${id}`, { method: 'PUT', body: JSON.stringify(body) });
export const deleteNotificationPreset = (id: number) =>
  request<void>(`/api/presets/notifications/${id}`, { method: 'DELETE' });
export const testNotificationPreset = (id: number) =>
  request<{ ok: boolean; sent: string[]; errors: string[] }>(`/api/presets/notifications/${id}/test`, { method: 'POST' });

const NOTIFICATION_PROVIDER_LABELS: Record<string, string> = {
  web: 'Web Push',
  ntfy: 'ntfy',
  gotify: 'Gotify',
  telegram: 'Telegram',
  homeassistant: 'Home Assistant',
  apprise: 'Apprise',
  discord: 'Discord',
  slack: 'Slack',
};

export function splitNotificationProviders(provider: string) {
  return provider.split(',').map((s) => s.trim()).filter(Boolean);
}

export function formatNotificationProvider(provider: string) {
  return NOTIFICATION_PROVIDER_LABELS[provider] ?? provider;
}

export function formatNotificationProviders(provider: string) {
  return splitNotificationProviders(provider).map(formatNotificationProvider).join(' · ');
}

// Schedules
export const getSchedules = () => request<Schedule[]>('/api/schedules');
export const createSchedule = (body: Omit<Schedule, 'id' | 'created_at' | 'last_run_at' | 'next_run_at' | 'last_tick_status' | 'last_tick_reason' | 'last_task_id' | 'filter_preset_name' | 'effect_preset_name' | 'notification_preset_names'>) =>
  request<Schedule>('/api/schedules', { method: 'POST', body: JSON.stringify(body) });
export const updateSchedule = (id: number, body: Omit<Schedule, 'id' | 'created_at' | 'last_run_at' | 'next_run_at' | 'last_tick_status' | 'last_tick_reason' | 'last_task_id' | 'filter_preset_name' | 'effect_preset_name' | 'notification_preset_names'>) =>
  request<Schedule>(`/api/schedules/${id}`, { method: 'PUT', body: JSON.stringify(body) });
export const deleteSchedule = (id: number) =>
  request<void>(`/api/schedules/${id}`, { method: 'DELETE' });
export const triggerScheduleNow = (id: number) =>
  request<{ message: string; task_id: string }>(`/api/schedules/${id}/run-now`, { method: 'POST' });
