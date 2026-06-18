import { request } from './base';
import { type DetailedHealth } from './types';

export function getHealth() {
  return request<{ status: string; version: string; auth_enabled: boolean }>(
    '/api/health',
  );
}

export function getDetailedHealth() {
  return request<DetailedHealth>('/api/health/detailed');
}
