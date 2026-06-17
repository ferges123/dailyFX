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
  display_group?: string | null;
  default_weight: number;
  default_config: Record<string, unknown>;
  config_schema: GenerationModuleConfigField[];
};

export type StudioPreviewResponse = {
  task_id: string;
  history_url: string;
  image_url: string;
  module_name: string;
  title: string;
  summary: string;
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
  output_format?: 'png' | 'gif' | 'webp';
  frame_count?: number | null;
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

export type PushSubscriptionInfo = {
  id: number;
  endpoint_preview: string;
  device_label: string | null;
  user_agent: string | null;
  created_at: string;
};

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
  push_subscription_ids: number[];
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
