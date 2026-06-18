import { request } from './base';
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

export function getProviderModels(provider: string) {
  return request<{
    vision_models: Array<{ label: string; value: string }>;
    image_models: Array<{ label: string; value: string }>;
  }>(`/api/settings/models/${provider}`);
}
