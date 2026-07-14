import { request, requestText } from './base';
import {
  type Settings,
  type SettingsUpdate,
  type ConnectionTest,
} from './types';

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

export function testProviderConnection(provider: string) {
  return request<ConnectionTest>(`/api/settings/test-provider/${provider}`, {
    method: 'POST',
  });
}

export function getProviderModels(provider: string) {
  return request<{
    vision_models: Array<{ label: string; value: string }>;
    image_models: Array<{ label: string; value: string }>;
  }>(`/api/settings/models/${provider}`);
}

export function getDebugLog() {
  return requestText('/api/debug/log');
}

export type RetentionPreview = { files: number; metadata: number; tasks: number; bytes: number; missing_files: number; orphan_files: number; warnings: string[] };
export function getRetentionPreview() { return request<RetentionPreview>('/api/settings/retention/preview'); }
export function runRetention(dryRun = true) { return request<RetentionPreview>(`/api/settings/retention/run?dry_run=${dryRun}`, { method: 'POST' }); }
